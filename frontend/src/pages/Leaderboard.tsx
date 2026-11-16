import React, { useEffect, useState } from 'react';
import { Card, Empty, Table, Tag } from 'antd';
import { getLeaderboard } from '@/services/api';

const LeaderboardPage: React.FC = () => {
  const [rows, setRows] = useState<Array<Record<string, any>>>([]);
  useEffect(() => { void getLeaderboard().then((data) => setRows(data.rows)).catch(() => setRows([])); }, []);
  return <Card title="排行榜" extra={<Tag color="gold">按 RMSE 排名</Tag>}>
    {rows.length === 0 ? <Empty description="完成实验后，排行榜将在这里显示" /> : <Table rowKey="task_id" dataSource={rows} columns={[{ title: '排名', dataIndex: 'rank' }, { title: '实验', dataIndex: 'name' }, { title: 'RMSE（°）', dataIndex: 'rmse', render: (value: number) => value.toFixed(4) }]} />}
  </Card>;
};

export default LeaderboardPage;
