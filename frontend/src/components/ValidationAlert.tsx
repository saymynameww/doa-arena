import React from 'react';
import { Alert, Space } from 'antd';
import { WarningOutlined, CloseCircleOutlined } from '@ant-design/icons';
import type { ValidationError } from '@/utils/validation';

interface ValidationAlertProps {
  errors: ValidationError[];
}

/**
 * 校验提示组件
 *
 * 显示错误和警告信息
 */
const ValidationAlert: React.FC<ValidationAlertProps> = ({ errors }) => {
  if (errors.length === 0) {
    return null;
  }

  const errorMessages = errors.filter((e) => e.severity === 'error');
  const warningMessages = errors.filter((e) => e.severity === 'warning');

  return (
    <Space direction="vertical" style={{ width: '100%', marginBottom: 16 }}>
      {errorMessages.length > 0 && (
        <Alert
          message="配置错误"
          description={
            <ul style={{ margin: 0, paddingLeft: 20 }}>
              {errorMessages.map((error, index) => (
                <li key={index}>{error.message}</li>
              ))}
            </ul>
          }
          type="error"
          showIcon
          icon={<CloseCircleOutlined />}
        />
      )}

      {warningMessages.length > 0 && (
        <Alert
          message="配置警告"
          description={
            <ul style={{ margin: 0, paddingLeft: 20 }}>
              {warningMessages.map((warning, index) => (
                <li key={index}>{warning.message}</li>
              ))}
            </ul>
          }
          type="warning"
          showIcon
          icon={<WarningOutlined />}
          closable
        />
      )}
    </Space>
  );
};

export default ValidationAlert;
