import React from 'react';
import { Button, Dropdown, message } from 'antd';
import { DownloadOutlined } from '@ant-design/icons';
import type { MenuProps } from 'antd';
import { downloadTaskExport } from '@/services/api';

interface ExportMenuProps {
  taskId: string;
  resultPath?: string;
}

/**
 * 导出菜单组件
 *
 * 提供多种格式的数据和报告导出
 */
const ExportMenu: React.FC<ExportMenuProps> = ({ taskId }) => {
  const handleExport = async (format: string) => {
    try {
      message.loading({ content: `正在导出 ${format.toUpperCase()}...`, key: 'export' });

      const blob = await downloadTaskExport(taskId, format);
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `experiment_${taskId}.${format}`;
      link.click();
      URL.revokeObjectURL(url);

      message.success({ content: `${format.toUpperCase()} 已导出`, key: 'export' });

    } catch (error) {
      message.error({ content: '导出失败', key: 'export' });
    }
  };

  const menuItems: MenuProps['items'] = [
    {
      key: 'data',
      type: 'group',
      label: '数据格式',
      children: [
        {
          key: 'csv',
          label: 'CSV 表格',
          onClick: () => handleExport('csv'),
        },
        {
          key: 'mat',
          label: 'MATLAB (.mat)',
          onClick: () => handleExport('mat'),
        },
        {
          key: 'npz',
          label: 'NumPy (.npz)',
          onClick: () => handleExport('npz'),
        },
        {
          key: 'json',
          label: 'JSON',
          onClick: () => handleExport('json'),
        },
      ],
    },
    {
      key: 'divider1',
      type: 'divider',
    },
    {
      key: 'charts',
      type: 'group',
      label: '图表格式',
      children: [
        {
          key: 'html',
          label: 'HTML 报告（离线）',
          onClick: () => handleExport('html'),
        },
        {
          key: 'png',
          label: 'PNG 图像',
          onClick: () => handleExport('png'),
        },
        {
          key: 'svg',
          label: 'SVG 矢量图',
          onClick: () => handleExport('svg'),
        },
        {
          key: 'pdf',
          label: 'PDF 文档',
          onClick: () => handleExport('pdf'),
        },
      ],
    },
    {
      key: 'divider2',
      type: 'divider',
    },
    {
      key: 'latex',
      label: 'LaTeX 表格',
      onClick: () => handleExport('tex'),
    },
    {
      key: 'script',
      label: '脚本代码（可复现）',
      onClick: () => handleExport('py'),
    },
  ];

  return (
    <Dropdown menu={{ items: menuItems }} placement="bottomRight">
      <Button icon={<DownloadOutlined />}>导出</Button>
    </Dropdown>
  );
};

export default ExportMenu;
