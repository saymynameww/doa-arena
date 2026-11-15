import React from 'react';
import { Card } from 'antd';

interface ScenePreviewProps {
  arraySize?: number;
  sourceAngles?: number[];
  sourceRanges?: Array<{ min: number; max: number }>; // 动态范围
  faultyElements?: number[];
}

/**
 * 场景预览组件
 *
 * 显示阵列布局和信源方向的可视化
 */
const ScenePreview: React.FC<ScenePreviewProps> = ({
  arraySize = 16,
  sourceAngles = [-20, 20],
  sourceRanges = [],
  faultyElements = [],
}) => {
  const width = 300;
  const height = 200;
  const centerX = width / 2;
  const centerY = height - 20;
  const radius = 120;

  // 绘制半圆刻度
  const renderScale = () => {
    const angles = [-90, -60, -30, 0, 30, 60, 90];
    return angles.map((angle) => {
      const rad = (angle * Math.PI) / 180;
      const x = centerX + radius * Math.sin(rad);
      const y = centerY - radius * Math.cos(rad);

      return (
        <g key={angle}>
          <line
            x1={centerX}
            y1={centerY}
            x2={x}
            y2={y}
            stroke="#d9d9d9"
            strokeWidth="1"
            strokeDasharray="2,2"
          />
          <text
            x={x}
            y={y - 10}
            textAnchor="middle"
            fontSize="10"
            fill="#8c8c8c"
          >
            {angle}°
          </text>
        </g>
      );
    });
  };

  // 绘制阵列元
  const renderArrayElements = () => {
    const elements = [];
    const spacing = 10; // 阵元间距

    for (let i = 0; i < arraySize; i++) {
      const x = centerX - ((arraySize - 1) * spacing) / 2 + i * spacing;
      const y = centerY;
      const isFaulty = faultyElements.includes(i);

      elements.push(
        <g key={i}>
          <circle
            cx={x}
            cy={y}
            r="4"
            fill={isFaulty ? '#ff4d4f' : '#1890ff'}
            stroke={isFaulty ? '#cf1322' : '#096dd9'}
            strokeWidth="1"
          />
          {isFaulty && (
            <line
              x1={x - 3}
              y1={y - 3}
              x2={x + 3}
              y2={y + 3}
              stroke="#fff"
              strokeWidth="1.5"
            />
          )}
        </g>
      );
    }

    return elements;
  };

  // 绘制信源方向
  const renderSources = () => {
    return sourceAngles.map((angle, index) => {
      const rad = (angle * Math.PI) / 180;
      const x = centerX + radius * Math.sin(rad);
      const y = centerY - radius * Math.cos(rad);
      const hasRange = sourceRanges[index];

      return (
        <g key={index}>
          {/* 如果有动态范围，绘制扇形区域 */}
          {hasRange && (
            <path
              d={createArcPath(
                centerX,
                centerY,
                radius * 0.9,
                hasRange.min,
                hasRange.max
              )}
              fill="#52c41a"
              fillOpacity="0.15"
              stroke="#52c41a"
              strokeWidth="1"
              strokeDasharray="3,3"
            />
          )}

          {/* 信源方向线 */}
          <line
            x1={centerX}
            y1={centerY}
            x2={x}
            y2={y}
            stroke="#52c41a"
            strokeWidth="2"
            markerEnd="url(#arrowhead)"
          />
          <circle cx={x} cy={y} r="6" fill="#52c41a" />
          <text
            x={x}
            y={y - 15}
            textAnchor="middle"
            fontSize="12"
            fontWeight="bold"
            fill="#52c41a"
          >
            {angle}°
            {hasRange && <tspan fontSize="9" fill="#8c8c8c"> (范围)</tspan>}
          </text>
        </g>
      );
    });
  };

  // 创建扇形路径
  const createArcPath = (
    cx: number,
    cy: number,
    r: number,
    startAngle: number,
    endAngle: number
  ): string => {
    const startRad = (startAngle * Math.PI) / 180;
    const endRad = (endAngle * Math.PI) / 180;

    const x1 = cx + r * Math.sin(startRad);
    const y1 = cy - r * Math.cos(startRad);
    const x2 = cx + r * Math.sin(endRad);
    const y2 = cy - r * Math.cos(endRad);

    const largeArcFlag = endAngle - startAngle > 180 ? 1 : 0;

    return `
      M ${cx} ${cy}
      L ${x1} ${y1}
      A ${r} ${r} 0 ${largeArcFlag} 1 ${x2} ${y2}
      Z
    `;
  };

  return (
    <Card title="场景预览" size="small">
      <svg width={width} height={height}>
        <defs>
          <marker
            id="arrowhead"
            markerWidth="10"
            markerHeight="10"
            refX="8"
            refY="3"
            orient="auto"
          >
            <polygon points="0 0, 10 3, 0 6" fill="#52c41a" />
          </marker>
        </defs>

        {/* 半圆刻度 */}
        {renderScale()}

        {/* 阵列元 */}
        {renderArrayElements()}

        {/* 信源方向 */}
        {renderSources()}

        {/* 图例 */}
        <g transform="translate(10, 20)">
          <circle cx="5" cy="5" r="4" fill="#1890ff" />
          <text x="15" y="9" fontSize="10" fill="#595959">
            阵元
          </text>

          <circle cx="5" cy="25" r="4" fill="#ff4d4f" />
          <line
            x1="2"
            y1="22"
            x2="8"
            y2="28"
            stroke="#fff"
            strokeWidth="1.5"
          />
          <text x="15" y="29" fontSize="10" fill="#595959">
            故障阵元
          </text>

          <line
            x1="0"
            y1="45"
            x2="10"
            y2="45"
            stroke="#52c41a"
            strokeWidth="2"
          />
          <text x="15" y="49" fontSize="10" fill="#595959">
            信源方向
          </text>
        </g>
      </svg>
    </Card>
  );
};

export default ScenePreview;
