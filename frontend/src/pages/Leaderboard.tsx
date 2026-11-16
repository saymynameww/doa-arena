import React from 'react';
import { Card, Empty, Tag } from 'antd';

const LeaderboardPage: React.FC = () => (
  <Card
    title="排行榜"
    extra={<Tag color="gold">P1</Tag>}
  >
    <Empty description="选择场景集后运行评测，排行榜将在这里显示" />
  </Card>
);

export default LeaderboardPage;
