'use client';

import { useState } from 'react';
import axios from 'axios';

interface UploadZoneProps {
  onUploadStart: (jobId: string) => void;
  onUploadError: (error: string) => void;
}

export default function UploadZone({ onUploadStart, onUploadError }: UploadZoneProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [email, setEmail] = useState('');
  const [ratePerDay, setRatePerDay] = useState(1000);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      handleFile(files[0]);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      handleFile(e.target.files[0]);
    }
  };

  const handleFile = async (file: File) => {
    if (!email.trim()) {
      onUploadError('Please enter your email address');
      return;
    }

    if (!file.name.endsWith('.zip')) {
      onUploadError('Please upload a .zip file');
      return;
    }

    setIsLoading(true);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('email', email);
    formData.append('rate_per_day', ratePerDay.toString());

    try {
      const response = await axios.post(
        `${process.env.NEXT_PUBLIC_API_URL}/api/v1/analyze`,
        formData,
        {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
        }
      );

      onUploadStart(response.data.job_id);
    } catch (error) {
      const errorMessage = axios.isAxiosError(error)
        ? error.response?.data?.detail || 'Upload failed'
        : 'An error occurred';
      onUploadError(errorMessage);
      setIsLoading(false);
    }
  };

  return (
    <div className="w-full max-w-2xl mx-auto">
      <div className="space-y-6">
        {/* Email Input */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Email Address
          </label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="your@company.com"
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
            disabled={isLoading}
          />
        </div>

        {/* Rate Per Day */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Rate per Engineer-Day ($)
          </label>
          <input
            type="number"
            value={ratePerDay}
            onChange={(e) => setRatePerDay(parseInt(e.target.value))}
            min="100"
            step="100"
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
            disabled={isLoading}
          />
          <p className="text-xs text-gray-500 mt-1">Used to calculate cost estimate</p>
        </div>

        {/* Upload Zone */}
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          className={`border-2 border-dashed rounded-lg p-12 text-center transition ${
            isDragging
              ? 'border-purple-500 bg-purple-50'
              : 'border-gray-300 hover:border-purple-400'
          } ${isLoading ? 'opacity-50 cursor-not-allowed' : ''}`}
        >
          <svg
            className="mx-auto h-12 w-12 text-gray-400"
            stroke="currentColor"
            fill="none"
            viewBox="0 0 48 48"
          >
            <path
              d="M28 8H12a4 4 0 00-4 4v20a4 4 0 004 4h24a4 4 0 004-4V20m-8-8l-4-4m0 0l-4 4m4-4v12"
              strokeWidth={2}
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>

          <p className="mt-4 text-lg font-medium text-gray-900">
            Drop your Oracle DDL + PL/SQL zip file here
          </p>
          <p className="mt-2 text-sm text-gray-500">
            or
          </p>

          <label className="mt-4 inline-block">
            <span className="bg-purple-600 text-white px-4 py-2 rounded-lg cursor-pointer hover:bg-purple-700 transition">
              {isLoading ? 'Analyzing...' : 'Select File'}
            </span>
            <input
              type="file"
              accept=".zip"
              onChange={handleFileSelect}
              className="hidden"
              disabled={isLoading}
            />
          </label>

          <p className="mt-2 text-xs text-gray-500">
            Maximum file size: 10 MB
          </p>
        </div>
      </div>
    </div>
  );
}
