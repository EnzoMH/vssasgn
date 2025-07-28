import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import React from "react";

interface InventoryChartProps {
  data: Array<{
    rackName: string;
    currentStock: number;
    capacity: number;
  }>;
}

const InventoryChart: React.FC<InventoryChartProps> = ({ data }) => {
  if (!data || data.length === 0) return <div>재고 데이터 없음</div>;

  return (
    <div className="chart-container">
      <h3 className="text-lg font-semibold mb-2">랙별 재고 현황</h3>
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={data}>
          <XAxis dataKey="rackName" />
          <YAxis />
          <Tooltip />
          <Legend />
          <Bar dataKey="currentStock" fill="#3B82F6" name="현재 재고" />
          <Bar dataKey="capacity" fill="#E5E7EB" name="최대 용량" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
};

export default InventoryChart;
