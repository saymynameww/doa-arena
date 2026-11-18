import { useEffect, useState } from "react";
import {
  Card,
  Input,
  Select,
  Button,
  message,
  Table,
  Tag,
  Descriptions,
  Space,
  Modal,
  Alert,
} from "antd";
import {
  addWorkspace,
  getAlgorithmSources,
  getCurrentWorkspace,
  getSettings,
  getWorkspaces,
  rebuildWorkspaceIndex,
  selectWorkspace,
  updateSettings,
  removeWorkspace,
} from "@/services/api";
import useEnvironment from "@/hooks/useEnvironment";

export default function SettingsPage() {
  const [workspaces, setWorkspaces] = useState<Array<Record<string, any>>>([]);
  const [current, setCurrent] = useState<Record<string, any>>({});
  const [sources, setSources] = useState<any[]>([]);
  const [settings, setSettings] = useState<Record<string, any>>({});
  const { environment, refresh, deviceLabel } = useEnvironment();
  const [failures, setFailures] = useState<any[]>([]);
  const [dialog, setDialog] = useState<"workspace" | "source">();
  const [path, setPath] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const act = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    try {
      await fn();
    } catch (e: any) {
      message.error(
        e.response?.data?.detail || "操作失败，请检查路径和服务状态",
      );
    } finally {
      setBusy(false);
    }
  };
  const load = async () => {
    const [ws, c, s, a] = await Promise.all([
      getWorkspaces(),
      getCurrentWorkspace(),
      getSettings(),
      getAlgorithmSources(),
    ]);
    setWorkspaces(ws);
    setCurrent(c);
    setSettings(s);
    setSources(a.sources);
    setFailures(a.failures);
  };
  useEffect(() => {
    void act(load);
  }, []);
  const open = (type: "workspace" | "source") => {
    setPath("");
    setName("");
    setDialog(type);
  };
  return (
    <Space direction="vertical" size="large" style={{ width: "100%" }}>
      <h2 style={{ margin: 0 }}>设置</h2>
      <Card
        title="工作目录"
        extra={<Button onClick={() => open("workspace")}>添加工作目录</Button>}
      >
        <Table
          rowKey="path"
          size="small"
          pagination={{ pageSize: 5, hideOnSinglePage: true }}
          dataSource={workspaces}
          scroll={{ x: 900 }}
          columns={[
            {
              title: "名称 / 路径",
              render: (_, w) => (
                <>
                  <strong>{w.name}</strong>
                  {w.path === current.path && <Tag color="blue">当前</Tag>}
                  <div style={{ color: "#64748b", overflowWrap: "anywhere" }}>
                    {w.path}
                  </div>
                </>
              ),
            },
            { title: "实验数", dataIndex: "experiments" },
            {
              title: "索引更新",
              render: (_, w) =>
                w.indexed_at
                  ? new Date(w.indexed_at * 1000).toLocaleString("zh-CN")
                  : "尚未建立",
            },
            {
              title: "状态",
              render: (_, w) => (
                <Tag color={w.exists ? "green" : "orange"}>
                  {w.exists ? "可用" : "尚未创建"}
                </Tag>
              ),
            },
            {
              title: "操作",
              render: (_, w) => (
                <Space wrap>
                  <Button
                    disabled={w.path === current.path}
                    onClick={() =>
                      void act(async () => {
                        await selectWorkspace(w);
                        window.location.reload();
                      })
                    }
                  >
                    切换
                  </Button>
                  <Button
                    disabled={w.path !== current.path}
                    onClick={() =>
                      void act(async () => {
                        const r = await rebuildWorkspaceIndex();
                        message.success(`索引已重建：${r.count} 个实验`);
                        await load();
                      })
                    }
                  >
                    重建索引
                  </Button>
                  <Button
                    disabled={w.path === current.path}
                    onClick={() =>
                      void act(async () => {
                        await removeWorkspace(w.path);
                        await load();
                      })
                    }
                  >
                    从列表移除
                  </Button>
                </Space>
              ),
            },
          ]}
        />
        <p style={{ color: "#64748b" }}>
          从列表移除仅取消登记，实验文件保留。重建索引会发现脚本生成的实验；需先切换到目标目录。
        </p>
      </Card>
      <Card
        title="算法来源"
        extra={<Button onClick={() => open("source")}>添加全局来源</Button>}
      >
        <Table
          rowKey={(r) => `${r.scope}:${r.value}`}
          pagination={false}
          size="small"
          dataSource={sources}
          columns={[
            { title: "层级", dataIndex: "scope" },
            { title: "名称", dataIndex: "name" },
            {
              title: "路径 / 入口",
              dataIndex: "value",
              render: (v) => (
                <span style={{ overflowWrap: "anywhere" }}>{v}</span>
              ),
            },
            { title: "已加载算法", dataIndex: "count" },
            { title: "操作", render: (_, source) => source.scope === "全局" && <Button danger onClick={() => Modal.confirm({ title: "移除此算法来源？", content: "只取消登记，不删除算法文件。", onOk: () => act(async () => { await updateSettings({ ...settings, algorithm_sources: (settings.algorithm_sources || []).filter((s: any) => s.value !== source.value || s.type !== source.type) }); await load(); }) })}>移除来源</Button> },
            {
              title: "状态",
              render: (_, s) => (
                <Tag color={s.status === "ok" ? "green" : "orange"}>
                  {s.status === "ok" ? "可用" : "加载失败"}
                </Tag>
              ),
            },
          ]}
          locale={{ emptyText: "未登记外部来源；内置算法随竞技场提供" }}
        />
        {failures.map((f, i) => (
          <Alert
            key={i}
            type="error"
            message={f.message}
            description={f.path}
          />
        ))}
        <p style={{ color: "#64748b" }}>
          工作目录来源在该目录的 arena_workspace.json
          中编辑；相对路径以该工作目录为基准。
        </p>
      </Card>
      <Card title="默认运行设备">
        <Space>
          <Select
            aria-label="默认运行设备"
            value={settings.default_device || "auto"}
            style={{ width: 180 }}
            onChange={(v) => setSettings({ ...settings, default_device: v })}
            options={[
              { value: "auto", label: "自动选择" },
              { value: "cpu", label: "CPU" },
              { value: "cuda", label: deviceLabel, disabled: environment.cuda_available !== true },
            ]}
          />
          <Button
            loading={busy}
            onClick={() =>
              void act(async () => {
                await updateSettings(settings);
                message.success("已保存，将用于新添加算法的设备默认值");
              })
            }
          >
            保存
          </Button>
        </Space>
        <p>用于支持设备参数的学习型算法；已有实验配置保持其记录的设备设置。</p>
      </Card>
      <Card
        title="运行环境"
        extra={
          <Space>
          <Button loading={environment.status === "detecting"} onClick={() => void refresh()}>
            重新检测
          </Button>
          <Button
            onClick={() =>
              void navigator.clipboard
                .writeText(JSON.stringify(environment, null, 2))
                .then(() => message.success("环境信息已复制"))
                .catch(() => message.error("复制失败，请手动选择文本"))
            }
          >
            复制环境信息
          </Button>
          </Space>
        }
      >
        <Alert showIcon style={{ marginBottom: 16 }}
          type={environment.status === "error" ? "error" : "info"}
          message={environment.status === "detecting" ? "正在后台检测环境，可继续配置实验"
            : environment.status === "error" ? environment.error : "环境检测完成"}
          description="结果在本次服务运行期间缓存。安装依赖或切换 Python 环境后请重启服务。"
        />
        <Descriptions column={2}>
          {Object.entries(environment.details || {}).map(([key, value]) => (
            <Descriptions.Item key={key} label={key}>
              {String(value)}
            </Descriptions.Item>
          ))}
        </Descriptions>
      </Card>
      <Modal
        title={dialog === "workspace" ? "添加工作目录" : "添加全局算法来源"}
        open={!!dialog}
        confirmLoading={busy}
        onCancel={() => setDialog(undefined)}
        okText="添加"
        cancelText="取消"
        onOk={() =>
          void act(async () => {
            if (!path.trim()) {
              message.error("请输入路径");
              return;
            }
            if (dialog === "workspace") await addWorkspace({ name, path });
            else
              await updateSettings({
                ...settings,
                algorithm_sources: [
                  ...(settings.algorithm_sources || []),
                  { name: name || path, type: "path", value: path },
                ],
              });
            await load();
            setDialog(undefined);
          })
        }
      >
        <Space direction="vertical" style={{ width: "100%" }}>
          <Input
            aria-label="名称"
            placeholder="名称（可选）"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <Input
            aria-label="目录路径"
            placeholder="本机目录的绝对路径"
            value={path}
            onChange={(e) => setPath(e.target.value)}
          />
          {dialog === "source" && (
            <Alert
              type="info"
              message="选择包含 arena_plugin.py 的算法目录；添加后在隔离进程发现插件。"
            />
          )}
        </Space>
      </Modal>
    </Space>
  );
}
