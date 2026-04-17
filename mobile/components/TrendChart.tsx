import React, { useMemo } from "react";
import { View, Text, StyleSheet, Dimensions } from "react-native";
import Svg, { Polyline, Circle, Line, Text as SvgText } from "react-native-svg";

interface TrendChartProps {
  label: string;              // "Heart Rate"
  unit: string;               // "BPM"
  values: (number | null)[];  // oldest → newest, nulls skipped
  height?: number;
  color?: string;
  formatter?: (v: number) => string;
}

const CARD_INNER_WIDTH = Dimensions.get("window").width - 48 - 32; // screen − screen-padding − card-padding
const LEFT_PAD = 8;
const RIGHT_PAD = 8;
const TOP_PAD = 18;   // room for value labels above dots
const BOTTOM_PAD = 4;

export default function TrendChart({
  label,
  unit,
  values,
  height = 90,
  color = "#FF4D6D",
  formatter,
}: TrendChartProps) {
  const width = CARD_INNER_WIDTH;

  // Keep only defined points, tracking original slot index so the x-axis
  // still reflects the chronological order of the last 5 scans even when
  // some are missing a particular metric.
  const indexed = values
    .map((v, i) => ({ v, i }))
    .filter((p): p is { v: number; i: number } => p.v != null && Number.isFinite(p.v));

  const { points, dots, yMin, yMax } = useMemo(() => {
    if (indexed.length === 0) return { points: "", dots: [], yMin: 0, yMax: 1 };

    const nums = indexed.map((p) => p.v);
    const min = Math.min(...nums);
    const max = Math.max(...nums);
    const span = max - min || 1;
    const pad = span * 0.2;
    const yLo = min - pad;
    const yHi = max + pad;

    const plotW = width - LEFT_PAD - RIGHT_PAD;
    const plotH = height - TOP_PAD - BOTTOM_PAD;

    // X anchors across all 5 slots so the spacing is fixed even if some
    // slots are missing — last reading lives on the right edge.
    const slotCount = Math.max(values.length, 1);
    const xFor = (slot: number) =>
      slotCount === 1 ? LEFT_PAD + plotW / 2 : LEFT_PAD + (slot / (slotCount - 1)) * plotW;
    const yFor = (val: number) => TOP_PAD + (1 - (val - yLo) / (yHi - yLo)) * plotH;

    const coords = indexed.map((p) => ({ x: xFor(p.i), y: yFor(p.v), v: p.v, i: p.i }));
    const poly = coords.map((c) => `${c.x.toFixed(1)},${c.y.toFixed(1)}`).join(" ");

    return { points: poly, dots: coords, yMin: yLo, yMax: yHi };
  }, [values, width, height]);

  if (indexed.length === 0) return null;

  const latest = indexed[indexed.length - 1].v;
  const previous = indexed.length > 1 ? indexed[indexed.length - 2].v : null;
  const delta = previous != null ? latest - previous : null;
  const deltaColor = delta == null ? "#666" : delta > 0 ? "#FB7185" : delta < 0 ? "#4ADE80" : "#888";
  const deltaSign = delta == null ? "" : delta > 0 ? "▲" : delta < 0 ? "▼" : "•";

  const fmt = formatter ?? ((n: number) => Math.round(n).toString());

  return (
    <View style={styles.wrap}>
      <View style={styles.headerRow}>
        <Text style={styles.label}>{label}</Text>
        <View style={styles.headerRight}>
          <Text style={styles.latestValue}>
            {fmt(latest)} <Text style={styles.latestUnit}>{unit}</Text>
          </Text>
          {delta != null && Math.abs(delta) > 0.01 && (
            <Text style={[styles.delta, { color: deltaColor }]}>
              {deltaSign} {fmt(Math.abs(delta))}
            </Text>
          )}
        </View>
      </View>
      <Svg width={width} height={height}>
        <Line
          x1={LEFT_PAD}
          y1={height - BOTTOM_PAD}
          x2={width - RIGHT_PAD}
          y2={height - BOTTOM_PAD}
          stroke="#222"
          strokeWidth={1}
        />
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
        {dots.map((d, i) => (
          <React.Fragment key={i}>
            <Circle cx={d.x} cy={d.y} r={3.5} fill={color} />
            <SvgText
              x={d.x}
              y={d.y - 7}
              fontSize={10}
              fontWeight="600"
              fill="#ccc"
              textAnchor="middle"
            >
              {fmt(d.v)}
            </SvgText>
          </React.Fragment>
        ))}
      </Svg>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { width: "100%", gap: 4 },
  headerRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  label: { color: "#aaa", fontSize: 13, fontWeight: "600" },
  headerRight: { flexDirection: "row", alignItems: "baseline", gap: 8 },
  latestValue: { color: "#fff", fontSize: 14, fontWeight: "700" },
  latestUnit: { color: "#888", fontSize: 11, fontWeight: "600" },
  delta: { fontSize: 11, fontWeight: "700" },
});
