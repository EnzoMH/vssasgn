import React from "react";
import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";

interface ProductCategoryChartProps {
  data: Array<{
    name: string;
    value: number;
  }>;
}

const COLORS = [
  "#0088FE",
  "#00C49F",
  "#FFBB28",
  "#FF8042",
  "#A28DFF",
  "#FF6B6B",
  "#6BFFB3",
];

const ProductCategoryChart: React.FC<ProductCategoryChartProps> = ({
  data,
}) => {
  if (!data || data.length === 0) return <div>상품 카테고리 데이터 없음</div>;

  return (
    <div className="chart-container">
      <h3 className="text-lg font-semibold mb-2">제품 카테고리별 분포</h3>
      <ResponsiveContainer width="100%" height={300}>
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            outerRadius={100}
            fill="#8884d8"
            dataKey="value"
            label={({ name, percent }) =>
              `${name} ${(percent * 100).toFixed(0)}%`
            }
          >
            {data.map((entry, index) => (
              <Cell
                key={`cell-${index}`}
                fill={COLORS[index % COLORS.length]}
              />
            ))}
          </Pie>
          <Tooltip />
          <Legend />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
};

export default ProductCategoryChart;
