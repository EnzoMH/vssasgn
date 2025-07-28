import React, { useState, useEffect } from "react";
import axios from "axios";
import KPICards from "./KPICards";
import InventoryChart from "./InventoryChart";
import TrendChart from "./TrendChart";
import ProductCategoryChart from "./ProductCategoryChart";
import AIChat from "./AIChat";
import FileUpload from "./FileUpload"; // 새로 추가

const API_BASE_URL = "http://localhost:8000/api";

const Dashboard: React.FC = () => {
  const [kpiData, setKpiData] = useState<any>(null);
  const [inventoryData, setInventoryData] = useState<any[]>([]);
  const [trendData, setTrendData] = useState<any[]>([]);
  const [productCategoryData, setProductCategoryData] = useState<any[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchDashboardData = async () => {
      try {
        const kpiResponse = await axios.get(`${API_BASE_URL}/dashboard/kpi`);
        setKpiData(kpiResponse.data);

        const inventoryResponse = await axios.get(
          `${API_BASE_URL}/inventory/by-rack`
        );
        setInventoryData(inventoryResponse.data);

        const trendResponse = await axios.get(`${API_BASE_URL}/trends/daily`);
        setTrendData(trendResponse.data);

        const productCategoryResponse = await axios.get(
          `${API_BASE_URL}/product/category-distribution`
        );
        setProductCategoryData(productCategoryResponse.data);
      } catch (err) {
        setError("데이터를 불러오는 데 실패했습니다.");
        console.error("Error fetching dashboard data:", err);
      } finally {
        setLoading(false);
      }
    };

    fetchDashboardData();
  }, []);

  if (loading) return <div>데이터 로딩 중...</div>;
  if (error) return <div>오류: {error}</div>;

  return (
    <div className="dashboard p-4">
      <h1 className="text-2xl font-bold mb-4">스마트 물류창고 대시보드</h1>
      <KPICards data={kpiData} />
      <div className="charts-grid grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mt-4">
        <div className="chart-container bg-white rounded-lg shadow-md p-4">
          <InventoryChart data={inventoryData} />
        </div>
        <div className="chart-container bg-white rounded-lg shadow-md p-4">
          <TrendChart data={trendData} />
        </div>
        <div className="chart-container bg-white rounded-lg shadow-md p-4">
          <ProductCategoryChart data={productCategoryData} />
        </div>
        <div className="col-span-1 md:col-span-2 lg:col-span-1 bg-white rounded-lg shadow-md p-4">
          <FileUpload />
        </div>{" "}
        {/* 파일 업로드 컴포넌트 추가 */}
        {/* AI Chat 컴포넌트도 추가 */}
        <div className="col-span-1 md:col-span-2 lg:col-span-1 bg-white rounded-lg shadow-md p-4">
          <AIChat />
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
