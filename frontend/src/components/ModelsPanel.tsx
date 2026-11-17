import { useEffect, useState } from "react";
import {
  Alert,
  Button,
  Card,
  Empty,
  Input,
  Modal,
  Space,
  Table,
  Tag,
  message,
} from "antd";
import { getModels, importModel, inspectModel } from "@/services/api";
import type { ModelRecord, ModelInspection } from "@/types/generated";

function describeValue(value: any): string {
  if (value == null) return "未记录";
  if (typeof value !== "object") return String(value);
  if (value.uniform || value.uniform_int)
    return `${(value.uniform || value.uniform_int).join(" 到 ")}（均匀分布）`;
  if (value.choice) return value.choice.join("、");
  return JSON.stringify(value);
}

export default function ModelsPanel() {
  const [models, setModels] = useState<ModelRecord[]>([]);
  const [failures, setFailures] = useState<string[]>([]);
  const [generatorVersion, setGeneratorVersion] = useState<number>();
  const [open, setOpen] = useState(false);
  const [path, setPath] = useState("");
  const [busy, setBusy] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [inspection, setInspection] = useState<ModelInspection | null>(null);
  const reload = async () => {
    const data = await getModels();
    setModels(data.models);
    setFailures(data.failures);
    setGeneratorVersion(data.generator_version);
  };
  useEffect(() => {
    void reload().catch(() => message.error("模型库加载失败"));
  }, []);
  const submit = async () => {
    setBusy(true);
    setErrorMessage("");
    try {
      if (!inspection) {
        setInspection(await inspectModel(path));
        return;
      }
      await importModel(path);
      await reload();
      setOpen(false);
      setPath("");
      setInspection(null);
      message.success("模型包已导入");
    } catch (error: any) {
      setErrorMessage(
        String(
          error.response?.data?.detail || "导入失败，请检查模型目录与权重哈希",
        ),
      );
    } finally {
      setBusy(false);
    }
  };
  return (
    <Card
      title="模型包"
      style={{ marginTop: 24 }}
      extra={<Button onClick={() => setOpen(true)}>导入模型包</Button>}
    >
      {failures.length > 0 && (
        <Alert type="warning" message={failures.join("；")} />
      )}
      {models.length === 0 && (
        <Empty description="尚未导入模型包。训练完成后导入包含 model.json 和权重的目录或 ZIP。" />
      )}
      {models.length > 0 && (
        <Table<ModelRecord>
          rowKey="path"
          size="small"
          dataSource={models}
          pagination={false}
          scroll={{ x: 1000 }}
          columns={[
            {
              title: "模型包",
              dataIndex: "name",
              render: (value) => <strong>{value}</strong>,
            },
            { title: "插件", dataIndex: "algorithm_id" },
            {
              title: "阵列",
              render: (_, model) => (
                <span>
                  {String((model.metadata.array as any)?.type)}
                  <br />
                  {Object.entries((model.metadata.array as any)?.params || {})
                    .map(([key, value]) => `${key}=${value}`)
                    .join("，")}
                </span>
              ),
            },
            {
              title: "训练条件",
              width: 240,
              render: (_, model) => {
                const scene = (model.metadata.trained_on as any)?.dataset_config
                  ?.scenario;
                return scene ? (
                  <span>
                    K：{describeValue(scene.sources?.K)}；SNR：
                    {describeValue(scene.sources?.snr_db)} dB；快拍数：
                    {describeValue(scene.snapshots)}
                    <br />
                    {scene.impairments?.length
                      ? "包含阵列误差（展开详情）"
                      : "无阵列误差"}
                  </span>
                ) : (
                  "未提供训练配置"
                );
              },
            },
            {
              title: "信号模型版本",
              render: (_, model) => {
                const version = (model.metadata.trained_on as any)
                  ?.generator_version;
                return (
                  <Tag
                    color={version === generatorVersion ? "green" : "orange"}
                  >
                    {version ?? "未记录"} ·{" "}
                    {version === generatorVersion
                      ? "与当前一致"
                      : `当前 ${generatorVersion}`}
                  </Tag>
                );
              },
            },
            {
              title: "权重校验",
              render: (_, model) => (
                <Tag
                  color={model.metadata.weights_verified ? "green" : "default"}
                >
                  {model.metadata.weights_verified ? "导入时通过" : "未记录"}
                </Tag>
              ),
            },
            {
              title: "训练平台",
              render: (_, model) => {
                const training = model.metadata.training as any;
                return (
                  [training?.platform, training?.gpu]
                    .filter(Boolean)
                    .join("，") || "未记录"
                );
              },
            },
            {
              title: "导入时间",
              render: (_, model) =>
                model.metadata.imported_at
                  ? new Date(String(model.metadata.imported_at)).toLocaleString(
                      "zh-CN",
                    )
                  : "未记录",
            },
          ]}
          expandable={{
            expandedRowRender: (model) => (
              <>
                <p style={{ overflowWrap: "anywhere" }}>
                  模型目录：{model.path}
                </p>
                <pre
                  style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}
                >
                  {JSON.stringify(model.metadata, null, 2)}
                </pre>
              </>
            ),
          }}
        />
      )}
      <p style={{ marginTop: 12, color: "#667085" }}>
        训练范围和信号模型版本在评测时检查；超出训练范围会提示。展开模型可查看完整元信息。
      </p>
      <Modal
        title="导入模型包"
        open={open}
        onCancel={() => setOpen(false)}
        onOk={() => void submit()}
        okText={inspection ? "确认导入" : "检查模型包"}
        confirmLoading={busy}
        okButtonProps={{ disabled: !path.trim() }}
      >
        <p>
          输入本机模型包目录或 ZIP
          的绝对路径。导入会校验权重，同名模型不会覆盖。
        </p>
        <Input
          value={path}
          onChange={(e) => {
            setPath(e.target.value);
            setInspection(null);
            setErrorMessage("");
          }}
          placeholder="模型包绝对路径"
        />
        {errorMessage && (
          <Alert
            type="error"
            showIcon
            message={errorMessage}
            style={{ marginTop: 12 }}
          />
        )}
        {inspection && (
          <Space direction="vertical" style={{ marginTop: 12 }}>
            <Alert type="success" message={inspection.checks.join("；")} />
            {inspection.warnings.map((warning) => (
              <Alert key={warning} type="warning" message={warning} />
            ))}
          </Space>
        )}
      </Modal>
    </Card>
  );
}
