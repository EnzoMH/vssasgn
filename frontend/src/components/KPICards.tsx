import React from "react";

interface KPICardsProps {
  data: {
    total_inventory: number;
    daily_throughput: number;
    rack_utilization: number;
    inventory_turnover: number;
  } | null;
}

const KPICards: React.FC<KPICardsProps> = ({ data }) => {
  if (!data) return null; // 데이터가 없으면 렌더링하지 않음

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      <div className="kpi-card bg-white rounded-lg shadow-md p-6">
        <h3 className="text-lg font-semibold text-gray-600">총 재고</h3>
        <p className="text-3xl font-bold text-blue-600">
          {data.total_inventory.toLocaleString()}
        </p>
      </div>
      <div className="kpi-card bg-white rounded-lg shadow-md p-6">
        <h3 className="text-lg font-semibold text-gray-600">일일 처리량</h3>
        <p className="text-3xl font-bold text-green-600">
          {data.daily_throughput.toLocaleString()}
        </p>
      </div>
      <div className="kpi-card bg-white rounded-lg shadow-md p-6">
        <h3 className="text-lg font-semibold text-gray-600">랙 활용률</h3>
        <p className="text-3xl font-bold text-yellow-600">
          {(data.rack_utilization * 100).toFixed(1)}%
        </p>
      </div>
      <div className="kpi-card bg-white rounded-lg shadow-md p-6">
        <h3 className="text-lg font-semibold text-gray-600">재고 회전율</h3>
        <p className="text-3xl font-bold text-purple-600">
          {data.inventory_turnover.toFixed(1)}
        </p>
      </div>
    </div>
  );
};

export default KPICards;
