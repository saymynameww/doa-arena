import React from "react";
import { Card } from "antd";

interface ScenePreviewProps {
  arraySize?: number;
  sourceAngles?: number[];
  sourceRanges?: Array<{ min: number; max: number }>; // 动态范围
  faultyElements?: number[];
  positions?: number[][];
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
  positions = [],
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
            x1={centerX + (radius + 5) * Math.sin(rad)}
            y1={centerY - (radius + 5) * Math.cos(rad)}
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
    const spacing = Math.min(10, (2 * radius) / Math.max(1, arraySize - 1)); // 限制预览宽度

    for (let i = 0; i < arraySize; i++) {
      const nominalSpan =
        Math.max(1, ...positions.map((p) => p[0])) -
        Math.min(0, ...positions.map((p) => p[0]));
      const x = positions[i]
        ? centerX -
          radius +
          (2 *
            radius *
            (positions[i][0] - Math.min(0, ...positions.map((p) => p[0])))) /
            nominalSpan
        : centerX - ((arraySize - 1) * spacing) / 2 + i * spacing;
      const y = centerY - (positions[i]?.[1] || 0) * 20;
      const isFaulty = faultyElements.includes(i);

      elements.push(
        <g key={i}>
          <circle
            cx={x}
            cy={y}
            r="4"
            fill={isFaulty ? "#ff4d4f" : "#667085"}
            stroke={isFaulty ? "#cf1322" : "#667085"}
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
        </g>,
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
                hasRange.max,
              )}
              fill="#24272c"
              fillOpacity="0.15"
              stroke="#24272c"
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
            stroke="#24272c"
            strokeWidth="2"
          />
          <circle cx={x} cy={y} r="3" fill="#24272c" />
          <text
            x={x}
            y={y - 15}
            textAnchor="middle"
            fontSize="12"
            fontWeight="bold"
            fill="#24272c"
          >
            {angle}°
            {hasRange && (
              <tspan fontSize="9" fill="#8c8c8c">
                {" "}
                (范围)
              </tspan>
            )}
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
    endAngle: number,
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
      <svg
        className="scene-preview-svg"
        viewBox={`0 0 ${width} ${height + 10}`}
        role="img"
        aria-label="阵列与信源方向预览"
      >
        <defs>
          <marker
            id="arrowhead"
            markerWidth="10"
            markerHeight="10"
            refX="8"
            refY="3"
            orient="auto"
          >
            <polygon points="0 0, 10 3, 0 6" fill="#24272c" />
          </marker>
        </defs>

        <path
          d={`M ${centerX - radius} ${centerY} A ${radius} ${radius} 0 0 1 ${centerX + radius} ${centerY}`}
          fill="none"
          stroke="#d3d8e0"
        />
        {/* 半圆刻度 */}
        {renderScale()}

        {/* 阵列元 */}
        {renderArrayElements()}

        {/* 信源方向 */}
        {renderSources()}
      </svg>
      <p className="scene-preview-caption">
        {sourceRanges.length
          ? "阴影为随机角度范围。"
          : `黑线是信源方向：${sourceAngles.map((angle) => `${angle}°`).join("、")}。`}
        {faultyElements.length > 0 ? "红点为已知故障阵元。" : ""}
        位置为第一个试验的示意。
      </p>
    </Card>
  );
};

export default ScenePreview;
