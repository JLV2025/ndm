#!/bin/bash
echo "启动前端服务..."
cd "$(dirname "$0")/../frontend"
npm run dev
