"""
Camera Calibration Tool for Daheng MER2-2000-19U3C
- แสดง Calibration Pattern (Checkerboard)
- ตรวจจับ Pattern และแสดง Status
- บันทึกค่า Calibration เป็นไฟล์
"""

import gxipy as gx
import cv2
import numpy as np
import json
import os
from datetime import datetime

# Configuration
CALIBRATION_PATTERN_SIZE = (8, 11)  # จำนวนจุดตัดของ Checkerboard (คอลัมน์-แถว)
SQUARE_SIZE = 12  # ขนาดตาราง (mm)
OUTPUT_DIR = "camera_configs"
CALIBRATION_FILE = os.path.join(OUTPUT_DIR, "calibration_data.json")
DEFAULT_CONFIG_FILE = os.path.join(OUTPUT_DIR, "config_default.raw")


def create_checkerboard_pattern(width=640, height=480, square_size=40):
    """สร้าง Checkerboard Pattern สำหรับแสดงบนหน้าจอ"""
    pattern = np.zeros((height, width, 3), dtype=np.uint8)
    
    rows = height // (square_size * 2)
    cols = width // (square_size * 2)
    
    for i in range(rows):
        for j in range(cols):
            y1 = i * square_size * 2
            y2 = y1 + square_size
            x1 = j * square_size * 2
            x2 = x1 + square_size
            
            if y2 > height or x2 > width:
                continue
                
            if (i + j) % 2 == 0:
                pattern[y1:y2, x1:x2] = (255, 255, 255)  # สีขาว
            else:
                pattern[y1:y2, x1:x2] = (0, 0, 0)  # สีดำ
    
    return pattern


def detect_checkerboard(image, pattern_size=CALIBRATION_PATTERN_SIZE):
    """ตรวจจับ Checkerboard Pattern ในภาพ"""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # หา Checkerboard corners
    found, corners = cv2.findChessboardCorners(gray, pattern_size, 
                                                cv2.CALIB_CB_ADAPTIVE_THRESH + 
                                                cv2.CALIB_CB_NORMALIZE_IMAGE)
    
    if found:
        # ปรับแต่งความละเอียดของจุดมุม
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
        corners = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
        
    return found, corners


def calculate_calibration(corners_list, image_size, pattern_size=CALIBRATION_PATTERN_SIZE, square_size=SQUARE_SIZE):
    """คำนวณค่า Calibration"""
    if len(corners_list) < 5:
        return None
    
    # สร้าง Object Points (จุดในโลกจริง)
    objp = np.zeros((pattern_size[0] * pattern_size[1], 3), np.float32)
    objp[:, :2] = np.mgrid[0:pattern_size[0], 0:pattern_size[1]].T.reshape(-1, 2)
    objp *= square_size
    
    objpoints = [objp] * len(corners_list)
    imgpoints = corners_list
    
    # คำนวณ Camera Matrix
    ret, mtx, dist, rvecs, tvecs = cv2.calibrateCamera(objpoints, imgpoints, image_size, None, None)
    
    if ret:
        return {
            "camera_matrix": mtx.tolist(),
            "distortion_coefficients": dist.tolist(),
            "rotation_vectors": [rvec.tolist() for rvec in rvecs],
            "translation_vectors": [tvec.tolist() for tvec in tvecs],
            "reprojection_error": ret,
            "image_size": image_size,
            "pattern_size": pattern_size,
            "square_size_mm": square_size
        }
    
    return None


def save_calibration_data(calib_data, filepath=CALIBRATION_FILE):
    """บันทึกค่า Calibration ลงไฟล์ JSON"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    data = {
        "calibration_date": datetime.now().isoformat(),
        "camera_model": "MER2-2000-19U3C",
        "calibration": calib_data
    }
    
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"[*] บันทึกค่า Calibration ไปที่: {filepath}")
    return filepath


def load_default_config(cam, config_file=DEFAULT_CONFIG_FILE):
    """โหลดการตั้งค่าพื้นฐานจากไฟล์ GenApi"""
    if os.path.exists(config_file):
        try:
            # อ่านไฟล์ config - ลองหลาย encoding
            content = ""
            for enc in ['utf-8', 'utf-16', 'utf-16-le', 'latin-1', 'cp1252']:
                try:
                    with open(config_file, 'r', encoding=enc, errors='ignore') as f:
                        content = f.read()
                    if len(content) > 100:  # ถ้าอ่านได้ content มากพอ
                        break
                except:
                    continue
            
            if not content:
                print(f"[!] ไม่สามารถอ่านไฟล์ config")
                return
            
            # หา section หลัง --->
            if '--->' in content:
                content = content.split('--->', 1)[1]
                # ตัด section ต่อไปถ้ามี
                if '--->' in content:
                    content = content.split('--->')[0]
            
            # Parse parameters
            params = {}
            lines = content.split('\n')
            
            for line in lines:
                line = line.strip()
                # ข้าม comment และ line ว่าง
                if not line or line.startswith('#') or line.startswith('<'):
                    continue
                
                # แยกด้วย tab
                if '\t' in line:
                    parts = line.split('\t')
                else:
                    parts = line.split()
                
                if len(parts) >= 2:
                    key = parts[0].strip()
                    value = parts[1].strip()
                    # ข้าม RegionSelector ที่ซ้ำ
                    if key and value and not key.startswith('Region'):
                        params[key] = value
            
            print(f"[*] พบ {len(params)} parameters")
            
            # Apply ทุกพารามีเตอร์ที่ parse ได้
            applied_count = 0
            failed_count = 0
            skipped_params = ['RegionSelector', 'DeviceLinkSelector', 'StreamSelector', 
                            'TimerDuration', 'TimerDelay', 'CounterResetSource',
                            'LUTSelector', 'LUTValue', 'ChunkSelector', 'LineSelector',
                            'UserOutputSelector', 'EventSelector', 'AAROIWidth', 'AAROIHeight',
                            'AAROIOffsetX', 'AAROIOffsetY', 'AWBROIWidth', 'AWBROIHeight',
                            'AWBROIOffsetX', 'AWBROIOffsetY', 'AutoExposureTimeMin', 'AutoExposureTimeMax',
                            'AutoGainMin', 'AutoGainMax', 'ExpectedGrayValue', 'BlackLevelSelector',
                            'GainSelector', 'BalanceRatioSelector', 'RemoveParameterLimit']
            
            for param_name, value in params.items():
                # ข้ามพารามีเตอร์ที่ไม่ต้องการ
                if param_name in skipped_params:
                    continue
                    
                try:
                    if not hasattr(cam, param_name):
                        continue
                    
                    # กำหนด type ของค่าตามพารามีเตอร์
                    if param_name in ['PixelFormat', 'AcquisitionMode', 'TriggerMode', 
                                     'TriggerSource', 'TriggerActivation', 'ExposureMode',
                                     'ExposureAuto', 'GainAuto', 'AWBLampHouse', 'GammaMode',
                                     'BlackLevelSelector', 'TestPattern', 'BinningSelector',
                                     'BinningHorizontalMode', 'BinningVerticalMode',
                                     'ReverseX', 'ReverseY', 'LineMode', 'LineSource',
                                     'UserOutputValue', 'TimerTriggerSource', 'BalanceWhiteAuto',
                                     'SaturationMode', 'ColorTransformationEnable', 
                                     'ColorTransformationMode', 'LightSourcePreset',
                                     'UserSetDefault', 'SensorShutterMode', 'RegionMode',
                                     'DecimationHorizontal', 'DecimationVertical',
                                     'StreamBufferHandlingMode', 'AcquisitionFrameRateMode',
                                     'DeviceLinkThroughputLimitMode', 'ChunkModeActive',
                                     'LUTEnable', 'AWBROIOffsetX', 'AWBROIOffsetY']:
                        # String values
                        cam[param_name].set(value)
                        applied_count += 1
                        print(f"   - {param_name}: {value}")
                        
                    elif param_name in ['Width', 'Height', 'OffsetX', 'OffsetY',
                                        'ExposureTime', 'TriggerDelay', 'TriggerFilterRaisingEdge',
                                        'TriggerFilterFallingEdge', 'BlackLevel', 'DigitalShift',
                                        'AcquisitionBurstFrameCount', 'BinningHorizontal', 
                                        'BinningVertical', 'LineInverter', 'UserOutputValue',
                                        'TimerDuration', 'TimerDelay', 'Saturation']:
                        # Integer values
                        cam[param_name].set(int(value))
                        applied_count += 1
                        print(f"   - {param_name}: {value}")
                        
                    elif param_name in ['Gain', 'AcquisitionFrameRate', 'BalanceRatio']:
                        # Float values
                        cam[param_name].set(float(value))
                        applied_count += 1
                        print(f"   - {param_name}: {value}")
                        
                    elif param_name in ['BalanceWhiteAuto']:
                        # Auto entry (On/Off/Once)
                        if value.lower() == 'on':
                            cam[param_name].set(gx.GxAutoEntry.ON)
                        elif value.lower() == 'off':
                            cam[param_name].set(gx.GxAutoEntry.OFF)
                        elif value.lower() == 'once':
                            cam[param_name].set(gx.GxAutoEntry.ONCE)
                        applied_count += 1
                        print(f"   - {param_name}: {value}")
                        
                    elif param_name in ['ColorTransformationEnable', 'GammaEnable']:
                        # Boolean values
                        cam[param_name].set(value.lower() == 'true' or value.lower() == '1')
                        applied_count += 1
                        print(f"   - {param_name}: {value}")
                        
                    else:
                        # ลองเป็น int ก่อน
                        try:
                            cam[param_name].set(int(value))
                            applied_count += 1
                            print(f"   - {param_name}: {value}")
                        except:
                            # ลองเป็น float
                            try:
                                cam[param_name].set(float(value))
                                applied_count += 1
                                print(f"   - {param_name}: {value}")
                            except:
                                # ลองเป็น string
                                try:
                                    cam[param_name].set(value)
                                    applied_count += 1
                                    print(f"   - {param_name}: {value}")
                                except:
                                    failed_count += 1
                                    
                except Exception as e:
                    failed_count += 1
            
            print(f"[*] โหลดการตั้งค่าพื้นฐาน: {applied_count} ค่า (ล้มเหลว: {failed_count} ค่า)")
            
        except Exception as e:
            print(f"[!] ไม่สามารถโหลด config: {e}")
            import traceback
            traceback.print_exc()
    else:
        print(f"[*] ไม่พบไฟล์ config: {config_file} (ข้าม)")


def draw_status_on_frame(frame, status, detected_count, required_count=5):
    """วาด Status บนหน้าจอ"""
    height, width = frame.shape[:2]
    
    # กรอบสถานะ
    cv2.rectangle(frame, (10, 10), (300, 80), (0, 0, 0), -1)
    cv2.rectangle(frame, (10, 10), (300, 80), (255, 255, 255), 2)
    
    # แสดงสถานะ
    if status == "DETECTED":
        color = (0, 255, 0)  # เขียว
        status_text = "✓ PATTERN DETECTED"
    elif status == "NOT_DETECTED":
        color = (0, 0, 255)  # แดง
        status_text = "✗ PATTERN NOT DETECTED"
    else:
        color = (255, 255, 0)  # เหลือง
        status_text = "○ WAITING FOR PATTERN"
    
    cv2.putText(frame, status_text, (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
    cv2.putText(frame, f"Captured: {detected_count}/{required_count}", (20, 60), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    
    # คำแนะนำ
    cv2.putText(frame, "[SPACE] Capture | [S] Save | [Q] Quit", (10, height - 20), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    
    return frame


def draw_corners_on_frame(frame, corners):
    """วาดจุดมุมที่ตรวจพบบนหน้าจอ"""
    if corners is not None:
        cv2.drawChessboardCorners(frame, CALIBRATION_PATTERN_SIZE, corners, True)
    return frame


def main():
    print("=" * 50)
    print("Camera Calibration Tool - Daheng MER2-2000-19U3C")
    print("=" * 50)
    
    # 1. เช็คและเปิดกล้อง
    device_manager = gx.DeviceManager()
    dev_num, dev_info_list = device_manager.update_device_list()

    if dev_num == 0:
        print("[!] ไม่พบกล้อง Daheng เชื่อมต่ออยู่")
        return

    # 2. เปิดกล้อง
    cam = device_manager.open_device_by_index(1)
    print(f"[*] เชื่อมต่อกล้อง: {dev_info_list[0].get('model_name')}")
    
    # 2.1 โหลดการตั้งค่าพื้นฐาน
    load_default_config(cam)
    
    # ขนาดภาพ
    width = cam.Width.get()
    height = cam.Height.get()
    print(f"[*] ขนาดภาพ: {width} x {height}")

    # 3. เริ่มแสดงภาพ
    cam.stream_on()
    
    # ตัวแปรสำหรับ Calibration
    captured_corners = []
    current_status = "WAITING"
    detected_count = 0
    calibration_done = False
    calib_result = None

    try:
        while True:
            # จับภาพ
            raw_image = cam.data_stream[0].get_image()
            if raw_image is None:
                continue

            # แปลงเป็น RGB แล้วเป็น OpenCV format
            rgb_image = raw_image.convert("RGB")
            if rgb_image is None:
                continue

            numpy_image = rgb_image.get_numpy_array()
            if numpy_image is None:
                continue

            frame = cv2.cvtColor(numpy_image, cv2.COLOR_RGB2BGR)
            
            # ย่อขนาดแสดงผล
            display_frame = cv2.resize(frame, (960, 640))
            
            # ตรวจจับ Checkerboard
            found, corners = detect_checkerboard(display_frame)
            
            if found:
                current_status = "DETECTED"
                # วาดจุดมุม
                display_frame = draw_corners_on_frame(display_frame, corners)
            else:
                current_status = "NOT_DETECTED"
            
            # วาด Status
            display_frame = draw_status_on_frame(display_frame, current_status, detected_count)
            
            # แสดงผล
            cv2.imshow("Camera Calibration", display_frame)
            
            # รับคำสั่ง
            key = cv2.waitKey(1) & 0xFF
            
            # กด Q = ออก
            if key == ord('q'):
                break
            
            # กด SPACE = จับภาพ Calibration
            if key == 32 and not calibration_done:  # Space
                if found:
                    captured_corners.append(corners)
                    detected_count += 1
                    print(f"[*] จับภาพที่ {detected_count} แล้ว")
                    
                    if detected_count >= 5:
                        # คำนวณ Calibration
                        image_size = (960, 640)
                        calib_result = calculate_calibration(captured_corners, image_size)
                        
                        if calib_result:
                            calibration_done = True
                            print(f"[*] Calibration เสร็จสิ้น! Error: {calib_result['reprojection_error']:.4f}")
                        else:
                            print("[!] คำนวณ Calibration ไม่สำเร็จ")
                else:
                    print("[!] ไม่พบ Pattern! กรุณาจัดแผ่นตารางให้ตรงกับกล้อง")
            
            # กด S = บันทึก
            if key == ord('s') and calibration_done:
                filepath = save_calibration_data(calib_result)
                print(f"[*] บันทึกไฟล์: {filepath}")
                
    except Exception as e:
        print(f"[!] Error: {e}")
    finally:
        cam.stream_off()
        cam.close_device()
        cv2.destroyAllWindows()
        print("[*] ปิดกล้องเรียบร้อย")


if __name__ == "__main__":
    main()