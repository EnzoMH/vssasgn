import React, { useState, useCallback } from "react";
import axios from "axios";
import { useDropzone } from "react-dropzone";

const API_BASE_URL = "http://localhost:8000/api";

const FileUpload: React.FC = () => {
  const [uploadStatus, setUploadStatus] = useState<string>("");
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    if (acceptedFiles.length === 0) {
      setError("파일을 선택해주세요.");
      return;
    }

    const file = acceptedFiles[0];
    const formData = new FormData();
    formData.append("file", file);

    setIsLoading(true);
    setUploadStatus("업로드 중...");
    setError(null);

    try {
      const response = await axios.post(
        `${API_BASE_URL}/upload/data`,
        formData,
        {
          headers: {
            "Content-Type": "multipart/form-data",
          },
        }
      );
      setUploadStatus(`성공: ${response.data.message}`);
    } catch (err: any) {
      console.error("파일 업로드 오류:", err);
      setUploadStatus("업로드 실패!");
      setError(
        err.response?.data?.detail ||
          "파일 업로드 중 알 수 없는 오류가 발생했습니다."
      );
    } finally {
      setIsLoading(false);
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    multiple: false, // 단일 파일만 허용
    accept: {
      "text/csv": [".csv"],
      "application/vnd.ms-excel": [".xls"],
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [
        ".xlsx",
      ],
    },
  });

  return (
    <div className="file-upload bg-white rounded-lg shadow-md p-6 flex flex-col items-center justify-center">
      <h3 className="text-lg font-semibold mb-4">데이터 파일 업로드</h3>
      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-lg p-10 text-center cursor-pointer transition-colors duration-200
          ${
            isDragActive
              ? "border-blue-500 bg-blue-50"
              : "border-gray-300 bg-gray-50"
          }`}
      >
        <input {...getInputProps()} />
        {isDragActive ? (
          <p className="text-blue-600">여기에 파일을 놓으세요...</p>
        ) : (
          <p className="text-gray-500">
            파일을 드래그앤드롭하거나 클릭하여 선택하세요 (CSV, XLSX)
          </p>
        )}
      </div>
      {isLoading && <p className="mt-4 text-blue-500">{uploadStatus}</p>}
      {uploadStatus && !isLoading && (
        <p className="mt-4 text-green-600">{uploadStatus}</p>
      )}
      {error && <p className="mt-4 text-red-500">오류: {error}</p>}
    </div>
  );
};

export default FileUpload;
