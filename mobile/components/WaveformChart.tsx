import React, { useMemo } from "react";
import { View, StyleSheet, Dimensions } from "react-native";
import Svg, { Polyline, Line, Rect } from "react-native-svg";

interface WaveformChartProps {
  data: number[];   // normalized [-1, 1]
  height?: number;
  color?: string;
}

const SCREEN_WIDTH = Dimensions.get("window").width;

export default function WaveformChart({
  data,
  height = 120,
  color = "#FF4D6D",
}: WaveformChartProps) {
  const width = SCREEN_WIDTH - 48; // 24px padding each side

  const points = useMemo(() => {
    if (!data || data.length === 0) return "";
    const xStep = width / (data.length - 1);
    const midY = height / 2;
    const amplitude = (height / 2) * 0.85;

    return data
      .map((v, i) => {
        const x = i * xStep;
        const y = midY - v * amplitude; // invert: positive = up
        return `${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(" ");
  }, [data, width, height]);

  return (
    <View style={[styles.container, { height }]}>
      <Svg width={width} height={height}>
        {/* Background */}
        <Rect x={0} y={0} width={width} height={height} fill="#1a1a1a" rx={12} />
        {/* Centre baseline */}
        <Line
          x1={0}
          y1={height / 2}
          x2={width}
          y2={height / 2}
          stroke="#333"
          strokeWidth={1}
          strokeDasharray="4,4"
        />
        {/* Signal */}
        {points ? (
          <Polyline
            points={points}
            fill="none"
            stroke={color}
            strokeWidth={2}
            strokeLinejoin="round"
            strokeLinecap="round"
          />
        ) : null}
      </Svg>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    alignItems: "center",
    justifyContent: "center",
  },
});
