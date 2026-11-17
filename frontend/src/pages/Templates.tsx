import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Card,
  Table,
  Button,
  Space,
  Tag,
  Modal,
  message,
  Select,
  Input,
  Dropdown,
  Alert,
} from "antd";
import { MoreOutlined } from "@ant-design/icons";
import {
  createTemplate,
  deleteTemplate,
  getTemplates,
  updateTemplate,
} from "@/services/api";
import type { Template } from "@/types";

const TemplatesPage: React.FC = () => {
  const navigate = useNavigate();
  const [templates, setTemplates] = useState<Template[]>([]);
  const [kind, setKind] = useState<string>();
  const [search, setSearch] = useState("");
  const [editing, setEditing] = useState<Template>();
  const load = () =>
    getTemplates()
      .then(setTemplates)
      .catch(() => message.error("加载模板失败"));
  useEffect(() => {
    void load();
  }, []);
  const act = (fn: () => Promise<unknown>) =>
    void fn().catch((e) =>
      message.error(e.response?.data?.detail || "操作失败，请重试"),
    );
  const copy = (t: Template) =>
    act(async () => {
      await createTemplate({
        ...t,
        id: undefined,
        level: "工作目录",
        name: `${t.name}（副本）`,
      });
      await load();
      message.success("已复制到工作目录");
    });
  const remove = (t: Template) =>
    Modal.confirm({
      title: `删除模板“${t.name}”？`,
      content: "模板将移入 .trash/，可手动恢复。",
      okText: "移入回收站",
      cancelText: "取消",
      onOk: async () => {
        await deleteTemplate(t.id);
        await load();
        message.success("模板已移入回收站");
      },
    });
  return (
    <Card
      title="模板"
      extra={
        <Button type="primary" onClick={() => navigate("/?saveTemplate=1")}>
          从新建实验保存模板
        </Button>
      }
    >
      <Alert
        type="info"
        message="场景模板只替换场景；完整实验模板替换场景、算法和运行设置。内置模板可复制后编辑。"
        style={{ marginBottom: 16 }}
      />
      <Space style={{ marginBottom: 16 }}>
        <Input
          placeholder="搜索模板名称或说明"
          allowClear
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <Select
          allowClear
          placeholder="全部模板类型"
          value={kind}
          onChange={setKind}
          style={{ width: 170 }}
          options={[
            { value: "scenario", label: "场景模板" },
            { value: "experiment", label: "完整实验模板" },
          ]}
        />
      </Space>
      <Table
        size="small"
        rowKey="id"
        dataSource={templates.filter(
          (t) =>
            (!kind || (t.kind || "experiment") === kind) &&
            `${t.name} ${t.description}`.includes(search),
        )}
        locale={{ emptyText: "暂无符合条件的模板" }}
        columns={[
          {
            title: "名称 / 说明",
            render: (_, t) => (
              <>
                <Button
                  type="link"
                  style={{ padding: 0 }}
                  onClick={() =>
                    navigate(`/?template=${encodeURIComponent(t.id)}`)
                  }
                >
                  {t.name}
                </Button>
                <div style={{ color: "#64748b" }}>{t.description}</div>
              </>
            ),
          },
          {
            title: "类型",
            render: (_, t) => (
              <Tag color={t.kind === "scenario" ? "blue" : "green"}>
                {t.kind === "scenario" ? "场景模板" : "完整实验"}
              </Tag>
            ),
          },
          { title: "层级", dataIndex: "level" },
          {
            title: "算法",
            render: (_, t) =>
              t.kind === "scenario"
                ? "保留当前算法"
                : (t.config?.algorithms?.length
                    ? t.config.algorithms.map((a) => a.label || a.id)
                    : t.algorithms
                  )?.join("、"),
          },
          {
            title: "修改时间",
            render: (_, t) =>
              t.level === "内置"
                ? "随竞技场"
                : t.createdAt
                  ? new Date(t.createdAt).toLocaleString("zh-CN")
                  : "未记录",
          },
          {
            title: "操作",
            render: (_, t) => (
              <Space>
                <Button
                  onClick={() =>
                    navigate(`/?template=${encodeURIComponent(t.id)}`)
                  }
                >
                  使用
                </Button>
                <Dropdown
                  menu={{
                    items: [
                      {
                        key: "copy",
                        label: "复制到工作目录",
                        onClick: () => copy(t),
                      },
                      ...(t.level === "内置"
                        ? []
                        : [
                            {
                              key: "edit",
                              label: "编辑名称和说明",
                              onClick: () => setEditing({ ...t }),
                            },
                            {
                              key: "config",
                              label: "编辑参数并保存新模板",
                              onClick: () =>
                                navigate(
                                  `/?template=${encodeURIComponent(t.id)}`,
                                ),
                            },
                            {
                              key: "delete",
                              label: "移入回收站",
                              danger: true,
                              onClick: () => remove(t),
                            },
                          ]),
                    ],
                  }}
                >
                  <Button aria-label="更多模板操作" icon={<MoreOutlined />} />
                </Dropdown>
              </Space>
            ),
          },
        ]}
      />
      <Modal
        title="编辑模板"
        open={!!editing}
        onCancel={() => setEditing(undefined)}
        onOk={() =>
          act(async () => {
            if (!editing?.name.trim()) throw Error("请输入名称");
            await updateTemplate(editing.id, editing);
            setEditing(undefined);
            await load();
          })
        }
        okText="保存"
        cancelText="取消"
      >
        <Space direction="vertical" style={{ width: "100%" }}>
          <Input
            aria-label="模板名称"
            value={editing?.name}
            onChange={(e) =>
              setEditing((t) => (t ? { ...t, name: e.target.value } : t))
            }
          />
          <Input.TextArea
            aria-label="模板说明"
            value={editing?.description}
            onChange={(e) =>
              setEditing((t) => (t ? { ...t, description: e.target.value } : t))
            }
          />
        </Space>
      </Modal>
    </Card>
  );
};
export default TemplatesPage;
