import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  Table,
  Card,
  Button,
  Tag,
  Space,
  message,
  Select,
  Input,
  Alert,
  Modal,
  Dropdown,
  Checkbox,
} from "antd";
import {
  ReloadOutlined,
  SearchOutlined,
  PlusOutlined,
  MoreOutlined,
  StarFilled,
  StarOutlined,
} from "@ant-design/icons";
import {
  cancelTask,
  getTasks,
  rerunTask,
  getExperimentNotes,
  saveExperimentNotes,
  downloadTaskExport,
} from "@/services/api";
import type { Task } from "@/types";
import type { ColumnsType } from "antd/es/table";
import ExperimentNotes from "@/components/ExperimentNotes";
import {
  compareReason,
  editExperiment,
  experimentModes,
} from "@/utils/experimentViews";

const HistoryPage: React.FC = () => {
  const navigate = useNavigate();
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [starred, setStarred] = useState(false);
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  async function load() {
    setLoading(true);
    try {
      setTasks(await getTasks());
      setLoadError("");
    } catch {
      setLoadError(
        "加载历史实验失败，请检查服务后刷新重试。已有实验不会因此删除。",
      );
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    void load();
  }, []);
  const filtered = tasks.filter(
    (t) =>
      (!starred || t.starred) &&
      (!filters.type || t.type === filters.type) &&
      (!filters.status || t.status === filters.status) &&
      (!filters.mode || t.mode === filters.mode) &&
      (!filters.tag || t.tags?.includes(filters.tag)) &&
      (!filters.algorithm ||
        t.config.algorithms?.some((a) => a.id === filters.algorithm)) &&
      `${t.name} ${t.task_id} ${t.notes} ${t.tags?.join(" ")}`
        .toLowerCase()
        .includes(search.toLowerCase()),
  );
  const reason = compareReason(
    tasks.filter((t) => selected.includes(t.task_id)),
  );
  const act = (fn: () => Promise<unknown>) =>
    void fn().catch((e) =>
      message.error(e.response?.data?.detail || "操作失败，请重试"),
    );
  const remove = (ids: string[]) =>
    Modal.confirm({
      title: `将 ${ids.length} 个实验移入回收站？`,
      content:
        "文件保存在当前工作目录的 .trash/ 中，可手动恢复。运行中的实验请先停止。",
      okText: "移入回收站",
      cancelText: "取消",
      onOk: async () => {
        for (const id of ids) await cancelTask(id);
        setSelected([]);
        await load();
      },
    });
  const statusNames: Record<string, string> = {
    queued: "等待中",
    running: "运行中",
    completed: "已完成",
    failed: "失败",
    cancelled: "已取消",
    interrupted: "已中断",
  };
  const columns: ColumnsType<Task> = [
    {
      title: "收藏",
      width: 56,
      render: (_, t) => (
        <Button
          type="text"
          aria-label={t.starred ? "取消收藏" : "收藏实验"}
          icon={
            t.starred ? (
              <StarFilled style={{ color: "#faad14" }} />
            ) : (
              <StarOutlined />
            )
          }
          onClick={(e) => {
            e.stopPropagation();
            act(async () => {
              const notes = await getExperimentNotes(t.task_id);
              await saveExperimentNotes(t.task_id, {
                ...notes,
                starred: !t.starred,
              });
              await load();
            });
          }}
        />
      ),
    },
    {
      title: "实验名称 / 备注 / 标签",
      dataIndex: "name",
      render: (_, t) => (
        <Space direction="vertical" size={2}>
          <Button
            type="link"
            style={{
              padding: 0,
              whiteSpace: "normal",
              height: "auto",
              textAlign: "left",
            }}
            onClick={() => navigate(`/runs/${t.task_id}`)}
          >
            {t.name || t.task_id}
          </Button>
          <span style={{ color: "#64748b" }}>{t.notes}</span>
          <span>
            {t.tags?.map((tag) => (
              <Tag key={tag}>{tag}</Tag>
            ))}
          </span>
        </Space>
      ),
    },
    {
      title: "创建时间",
      dataIndex: "created_at",
      width: 165,
      defaultSortOrder: "descend",
      sorter: (a, b) => a.created_at - b.created_at,
      render: (n) => new Date(n * 1000).toLocaleString("zh-CN"),
    },
    {
      title: "实验方式",
      width: 175,
      render: (_, t) => (
        <>
          <div>{experimentModes[t.type || "single"]}</div>
          <small>
            {t.type === "sweep"
              ? `${t.config.sweep?.label || t.config.sweep?.path} · ${t.config.sweep?.values.length} 点 × `
              : ""}
            {t.config.trials} 次
          </small>
        </>
      ),
    },
    {
      title: "算法",
      render: (_, t) =>
        t.config.algorithms
          ?.filter((a) => a.enabled !== false)
          .map((a) => <Tag key={a.label || a.id}>{a.label || a.id}</Tag>),
    },
    {
      title: "模式",
      width: 70,
      render: (_, t) =>
        t.mode === "web" ? "Web" : t.mode === "script" ? "脚本" : "未知",
    },
    {
      title: "状态",
      width: 90,
      render: (_, t) => (
        <Tag
          color={
            t.status === "completed"
              ? "success"
              : t.status === "failed"
                ? "error"
                : "default"
          }
        >
          {statusNames[t.status]}
        </Tag>
      ),
    },
    {
      title: "操作",
      width: 100,
      render: (_, t) => (
        <Space onClick={(e) => e.stopPropagation()}>
          <ExperimentNotes taskId={t.task_id} onComplete={() => void load()} />
          <Dropdown
            menu={{
              items: [
                {
                  key: "edit",
                  label: "复制并编辑",
                  onClick: () => {
                    editExperiment(t.config);
                    navigate("/");
                  },
                },
                {
                  key: "rerun",
                  label: "重新运行",
                  onClick: () =>
                    act(async () => {
                      const r = await rerunTask(t.task_id);
                      navigate(`/runs/${r.task_id}`);
                    }),
                },
                {
                  key: "script",
                  label: "导出复现脚本",
                  disabled: !t.has_results,
                  onClick: () =>
                    act(async () => {
                      const url = URL.createObjectURL(
                        await downloadTaskExport(t.task_id, "py"),
                      );
                      const a = document.createElement("a");
                      a.href = url;
                      a.download = `${t.task_id}.py`;
                      a.click();
                      URL.revokeObjectURL(url);
                    }),
                },
                {
                  key: "delete",
                  label: "移入回收站",
                  danger: true,
                  disabled: ["running", "queued"].includes(t.status),
                  onClick: () => remove([t.task_id]),
                },
              ],
            }}
          >
            <Button aria-label="更多实验操作" icon={<MoreOutlined />} />
          </Dropdown>
        </Space>
      ),
    },
  ];
  const filter = (
    key: string,
    placeholder: string,
    options: Array<{ value: string; label: string }>,
  ) => (
    <Select
      allowClear
      placeholder={placeholder}
      value={filters[key]}
      style={{ minWidth: 130 }}
      onChange={(v) => setFilters({ ...filters, [key]: v })}
      options={options}
    />
  );
  return (
    <Card
      title={`历史实验 · ${tasks.length} 个`}
      extra={
        <Space>
          <Button
            icon={<ReloadOutlined />}
            loading={loading}
            onClick={() => void load()}
          >
            刷新
          </Button>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => navigate("/")}
          >
            新建实验
          </Button>
        </Space>
      }
    >
      <Space wrap style={{ marginBottom: 20 }}>
        <Input
          aria-label="搜索实验"
          placeholder="搜索名称、备注或标签"
          prefix={<SearchOutlined />}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          allowClear
          style={{ width: 240 }}
        />
        {filter(
          "type",
          "全部实验方式",
          Object.entries(experimentModes).map(([value, label]) => ({
            value,
            label,
          })),
        )}
        {filter(
          "algorithm",
          "全部算法",
          Array.from(
            new Map(
              tasks.flatMap((t) =>
                (t.config.algorithms || []).map((a) => [a.id, a.label || a.id]),
              ),
            ),
          ).map(([value, label]) => ({ value, label })),
        )}
        {filter("mode", "全部运行模式", [
          { value: "web", label: "Web" },
          { value: "script", label: "脚本" },
        ])}
        {filter(
          "tag",
          "全部标签",
          Array.from(new Set(tasks.flatMap((t) => t.tags || []))).map(
            (value) => ({ value, label: value }),
          ),
        )}
        {filter(
          "status",
          "全部状态",
          Object.entries(statusNames).map(([value, label]) => ({
            value,
            label,
          })),
        )}
        <Checkbox
          checked={starred}
          onChange={(e) => setStarred(e.target.checked)}
        >
          仅收藏
        </Checkbox>
      </Space>
      {loadError && (
        <Alert
          type="error"
          showIcon
          message={loadError}
          style={{ marginBottom: 16 }}
        />
      )}
      <Table
        size="small"
        columns={columns}
        dataSource={filtered}
        loading={loading}
        rowKey="task_id"
        scroll={{ x: 1000 }}
        rowSelection={{
          selectedRowKeys: selected,
          onChange: (keys) => setSelected(keys as string[]),
        }}
        onRow={(t) => ({
          onClick: (e) => {
            if (
              !(e.target as HTMLElement).closest(
                "button,input,label,.ant-table-selection-column",
              )
            )
              navigate(`/runs/${t.task_id}`);
          },
        })}
        pagination={{
          defaultPageSize: 20,
          showSizeChanger: true,
          showTotal: (n) => `共 ${n} 个实验`,
        }}
        locale={{ emptyText: "没有符合条件的实验，请调整筛选或新建实验" }}
      />
      {selected.length > 0 && (
        <Alert
          style={{ position: "sticky", bottom: 16, zIndex: 2 }}
          message={`已选 ${selected.length} 个实验`}
          description={reason || "扫描变量一致，可以对比"}
          action={
            <Space>
              <Button
                type="primary"
                disabled={!!reason}
                onClick={() => navigate(`/compare?ids=${selected.join(",")}`)}
              >
                对比
              </Button>
              <Button
                danger
                disabled={tasks.some(
                  (t) =>
                    selected.includes(t.task_id) &&
                    ["queued", "running"].includes(t.status),
                )}
                onClick={() => remove(selected)}
              >
                移入回收站
              </Button>
              <Button onClick={() => setSelected([])}>取消选择</Button>
            </Space>
          }
        />
      )}
    </Card>
  );
};
export default HistoryPage;
