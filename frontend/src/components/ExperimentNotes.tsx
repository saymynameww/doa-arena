import { useEffect, useState } from "react";
import {
  Button,
  Card,
  Input,
  Modal,
  Select,
  Space,
  Switch,
  message,
} from "antd";
import { getExperimentNotes, saveExperimentNotes } from "@/services/api";
import type { ExperimentNotes as Notes } from "@/types/generated";

export default function ExperimentNotes({
  taskId,
  onComplete,
  inline = false,
}: {
  taskId: string;
  onComplete: () => void;
  inline?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notes, setNotes] = useState<Notes>({});
  useEffect(() => {
    if (inline)
      void getExperimentNotes(taskId)
        .then(setNotes)
        .catch(() => message.error("读取备注失败"));
  }, [taskId, inline]);
  const load = async () => {
    setBusy(true);
    try {
      setNotes(await getExperimentNotes(taskId));
      setOpen(true);
    } catch {
      message.error("读取备注失败");
    } finally {
      setBusy(false);
    }
  };
  const save = async () => {
    setBusy(true);
    try {
      await saveExperimentNotes(taskId, notes);
      setOpen(false);
      onComplete();
    } catch {
      message.error("保存备注失败");
    } finally {
      setBusy(false);
    }
  };
  const fields = (
    <Space direction="vertical" style={{ width: "100%" }}>
      <label>
        显示名称
        <Input
          value={notes.display_name ?? ""}
          onChange={(e) =>
            setNotes({ ...notes, display_name: e.target.value || null })
          }
        />
      </label>
      <label>
        备注
        <Input.TextArea
          value={notes.notes}
          rows={4}
          onChange={(e) => setNotes({ ...notes, notes: e.target.value })}
        />
      </label>
      <label>
        标签
        <Select
          mode="tags"
          style={{ width: "100%" }}
          value={notes.tags || []}
          onChange={(tags) => setNotes({ ...notes, tags })}
        />
      </label>
      <label>
        收藏{" "}
        <Switch
          checked={notes.starred}
          onChange={(starred) => setNotes({ ...notes, starred })}
        />
      </label>
    </Space>
  );
  if (inline)
    return (
      <Card title="备注与标签" size="small">
        {fields}
        <Button
          style={{ marginTop: 12 }}
          loading={busy}
          onClick={() => void save()}
        >
          保存备注
        </Button>
      </Card>
    );
  return (
    <>
      <Button
        type="link"
        size="small"
        loading={busy}
        onClick={() => void load()}
      >
        备注
      </Button>
      <Modal
        title="实验信息"
        open={open}
        onCancel={() => setOpen(false)}
        onOk={() => void save()}
        confirmLoading={busy}
        okText="保存"
        cancelText="取消"
      >
        {fields}
      </Modal>
    </>
  );
}
