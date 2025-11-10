import requests
from requests.auth import HTTPDigestAuth
import json
import os
import logging
from datetime import datetime
from pathlib import Path
import time
import cv2
import numpy as np


class HikvisionOpenCVCapture:
    def __init__(self, camera_ip, username, password, port=80, save_dir="captured_images"):
        self.camera_ip = camera_ip
        self.username = username
        self.password = password
        self.port = port
        self.save_dir = Path(save_dir)
        self.is_connected = False
        self.session = None
        self.base_url = f"http://{camera_ip}:{port}"

        self.save_dir.mkdir(parents=True, exist_ok=True)
        self.setup_logging()
        self.connect_camera()

    def setup_logging(self):
        """设置日志"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('camera_capture.log', encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def connect_camera(self):
        """连接摄像头"""
        try:
            self.session = requests.Session()
            self.session.auth = HTTPDigestAuth(self.username, self.password)

            test_url = f"{self.base_url}/ISAPI/System/deviceInfo"
            response = self.session.get(test_url, timeout=10)

            if response.status_code == 200:
                self.is_connected = True
                self.logger.info("✅ 摄像头连接成功")
                return True
            else:
                self.logger.error(f"❌ 摄像头连接失败: {response.status_code}")
                return False

        except Exception as e:
            self.logger.error(f"❌ 摄像头连接异常: {str(e)}")
            return False

    def capture_with_opencv(self, barcode_data, description=""):
        """
        使用OpenCV通过RTSP协议抓取高清图片
        """
        barcode_data = barcode_data.strip()

        if not barcode_data:
            return {"success": False, "message": "条码数据为空"}

        if not self.is_connected:
            return {"success": False, "message": "摄像头未连接"}

        # 检查OpenCV是否可用
        try:
            import cv2
        except ImportError:
            return {"success": False, "message": "OpenCV未安装"}

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        filename = f"CV_{barcode_data}_{timestamp}.jpg"
        save_path = self.save_dir / filename

        self.logger.info(f"🎯 OpenCV高清抓图开始，条码: {barcode_data}")

        # RTSP URL列表（按质量优先级排序）
        rtsp_urls = [
            # 主码流 - 最高质量
            f"rtsp://{self.username}:{self.password}@{self.camera_ip}:554/Streaming/Channels/101",
            f"rtsp://{self.username}:{self.password}@{self.camera_ip}:554/Streaming/Channels/1",
            # 备用URL
            f"rtsp://{self.username}:{self.password}@{self.camera_ip}:554/h264/ch1/main/av_stream",
            f"rtsp://{self.username}:{self.password}@{self.camera_ip}:554/ISAPI/Streaming/channels/101",
        ]

        best_result = None
        max_file_size = 0

        for i, rtsp_url in enumerate(rtsp_urls):
            try:
                self.logger.info(f"🔄 尝试RTSP URL {i + 1}: {rtsp_url}")

                result = self._capture_single_rtsp(rtsp_url, barcode_data, save_path, description, i + 1)

                if result["success"]:
                    file_size = result.get("file_size", 0)
                    self.logger.info(f"✅ RTSP {i + 1} 抓图成功，大小: {file_size} bytes")

                    # 记录最佳结果
                    if file_size > max_file_size:
                        max_file_size = file_size
                        best_result = result

                    # 如果获得高质量图片，直接返回
                    if file_size > 200 * 1024:  # 大于200KB认为是高质量
                        self.logger.info(f"🎉 获得高质量图片: {file_size} bytes")
                        return result

                else:
                    self.logger.warning(f"⚠️ RTSP {i + 1} 失败: {result.get('message', '未知错误')}")

            except Exception as e:
                self.logger.error(f"❌ RTSP {i + 1} 异常: {str(e)}")
                continue

        if best_result:
            return best_result
        else:
            return {"success": False, "message": "所有RTSP URL抓图都失败"}

    def _capture_single_rtsp(self, rtsp_url, barcode_data, save_path, description, method_num):
        """使用单个RTSP URL抓图"""
        cap = None
        try:
            self.logger.info(f"开始RTSP连接: {rtsp_url}")

            # 创建VideoCapture对象
            cap = cv2.VideoCapture(rtsp_url)

            if not cap.isOpened():
                return {"success": False, "message": "无法打开RTSP连接"}

            # 设置缓冲区大小为1，减少延迟
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

            # 设置分辨率（如果支持）
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)

            self.logger.info("RTSP连接成功，开始读取视频流...")

            # 读取多帧以确保获得清晰图片
            frames_captured = 0
            best_frame = None
            max_frame_quality = 0
            start_time = time.time()

            while time.time() - start_time < 15:  # 15秒超时
                ret, frame = cap.read()

                if ret and frame is not None:
                    frames_captured += 1

                    # 计算帧质量（基于图像清晰度）
                    frame_quality = self._calculate_frame_quality(frame)

                    # 记录质量最好的帧
                    if frame_quality > max_frame_quality:
                        max_frame_quality = frame_quality
                        best_frame = frame.copy()
                        self.logger.info(f"捕获第{frames_captured}帧，质量: {frame_quality:.2f}")

                    # 如果已经捕获足够多的帧且质量不错，提前退出
                    if frames_captured >= 10 and max_frame_quality > 100:
                        break

                    # 短暂延迟，避免过快读取
                    time.sleep(0.1)
                else:
                    self.logger.warning("读取帧失败或帧为空")
                    break

            # 释放摄像头资源
            cap.release()

            if best_frame is not None:
                self.logger.info(f"共捕获{frames_captured}帧，选择质量最好的帧保存")

                # 保存图片，最高质量
                temp_filename = f"temp_cv_{int(time.time() * 1000)}.jpg"
                temp_path = self.save_dir / temp_filename

                # 使用最高质量参数保存
                cv2.imwrite(str(temp_path), best_frame, [cv2.IMWRITE_JPEG_QUALITY, 100])

                if temp_path.exists():
                    file_size = os.path.getsize(temp_path)

                    # 重命名为最终文件
                    if save_path.exists():
                        save_path.unlink()
                    temp_path.rename(save_path)

                    # 保存抓图信息
                    info = self._save_capture_info(
                        barcode_data, save_path.name, save_path,
                        datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3],
                        description, f"opencv_rtsp_{method_num}", file_size
                    )

                    return {
                        "success": True,
                        "message": f"OpenCV RTSP抓图成功 (方法{method_num})",
                        "filename": save_path.name,
                        "file_path": str(save_path),
                        "file_size": file_size,
                        "file_size_kb": round(file_size / 1024, 1),
                        "barcode": barcode_data,
                        "quality": self._get_quality_level(file_size),
                        "method": f"opencv_rtsp_{method_num}",
                        "frames_captured": frames_captured,
                        "best_frame_quality": round(max_frame_quality, 2),
                        "info": info
                    }
                else:
                    return {"success": False, "message": "图片保存失败"}
            else:
                return {"success": False, "message": "未捕获到有效帧"}

        except Exception as e:
            # 确保释放资源
            if cap is not None:
                try:
                    cap.release()
                except:
                    pass
            return {"success": False, "message": f"RTSP抓图异常: {str(e)}"}

    def _calculate_frame_quality(self, frame):
        """计算帧质量（基于图像清晰度）"""
        try:
            # 转换为灰度图
            if len(frame.shape) == 3:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            else:
                gray = frame

            # 使用拉普拉斯方差法计算图像清晰度
            # 值越高表示图像越清晰
            laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()

            return laplacian_var

        except Exception as e:
            self.logger.warning(f"计算帧质量失败: {str(e)}")
            return 0

    def _get_quality_level(self, file_size):
        """获取质量等级"""
        if file_size > 500 * 1024:
            return "超高清"
        elif file_size > 200 * 1024:
            return "高清"
        elif file_size > 100 * 1024:
            return "标清"
        elif file_size > 50 * 1024:
            return "普通"
        else:
            return "低质量"

    def _save_capture_info(self, barcode_data, filename, save_path, timestamp, description, capture_method, file_size):
        """保存抓图信息"""
        info = {
            "barcode": barcode_data,
            "filename": filename,
            "file_path": str(save_path),
            "timestamp": timestamp,
            "description": description,
            "camera_ip": self.camera_ip,
            "capture_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            "capture_method": capture_method,
            "file_size": file_size,
            "file_size_kb": round(file_size / 1024, 1),
            "quality": self._get_quality_level(file_size)
        }

        record_path = self.save_dir / "capture_records.json"
        records = []

        if record_path.exists():
            try:
                with open(record_path, 'r', encoding='utf-8') as f:
                    records = json.load(f)
            except:
                records = []

        records.append(info)

        with open(record_path, 'w', encoding='utf-8') as f:
            json.dump(records, f, ensure_ascii=False, indent=2)

        return info

    def get_capture_history(self, limit=20):
        """获取抓图历史"""
        record_path = self.save_dir / "capture_records.json"

        if not record_path.exists():
            return []

        try:
            with open(record_path, 'r', encoding='utf-8') as f:
                records = json.load(f)

            records.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            return records[:limit]
        except Exception as e:
            self.logger.error(f"读取历史记录失败: {str(e)}")
            return []