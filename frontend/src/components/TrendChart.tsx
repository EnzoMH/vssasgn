import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import React from "react";

interface TrendChartProps {
  data: Array<{
    date: string;
    inbound: number;
    outbound: number;
  }>;
}

const TrendChart: React.FC<TrendChartProps> = ({ data }) => {
  if (!data || data.length === 0) return <div>트렌드 데이터 없음</div>;

  return (
    <div className="chart-container">
      <h3 className="text-lg font-semibold mb-2">일별 입출고 트렌드</h3>
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={data}>
          <XAxis dataKey="date" />
          <YAxis />
          <Tooltip />
          <Legend />
          <Line
            type="monotone"
            dataKey="inbound"
            stroke="#10B981"
            strokeWidth={2}
            name="입고"
          />
          <Line
            type="monotone"
            dataKey="outbound"
            stroke="#EF4444"
            strokeWidth={2}
            name="출고"
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
};

export default TrendChart;
