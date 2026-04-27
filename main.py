import gxipy as gx
import cv2
import os
import numpy as np

# --- CONFIGURATION ---
CONFIG_DIR = "camera_configs"
DEFAULT_CONFIG = os.path.join(CONFIG_DIR, "config_default.raw")

def ensure_config_dir():
    if not os.path.exists(CONFIG_DIR):
        os.makedirs(CONFIG_DIR)
        print(f"[*] สร้างโฟลเดอร์เก็บค่าเซ็ตติ้ง: {CONFIG_DIR}")

def main():
    ensure_config_dir()
    
    # 1. Initialize Device Manager
    device_manager = gx.DeviceManager()
    dev_num, dev_info_list = device_manager.update_device_list()

    if dev_num == 0:
        print("[!] ไม่พบกล้อง Daheng เชื่อมต่ออยู่ กรุณาเช็กสาย USB")
        return

    # 2. Open Camera (MER2-2000-19U3C)
    cam = device_manager.open_device_by_index(1)
    print(f"[*] เชื่อมต่อกล้องสำเร็จ: {dev_info_list[0].get('model_name')}")

    # 3. Load / Save Default Configuration
    if os.path.exists(DEFAULT_CONFIG):
        try:
            cam.import_config_file(DEFAULT_CONFIG)
            print(f"[*] โหลดค่า Config จากเวอร์ชันล่าสุดเรียบร้อย")
        except:
            print("[!] ไฟล์ Config เดิมเสียหาย กำลังสร้างใหม่...")
            cam.export_config_file(DEFAULT_CONFIG)
    else:
        cam.export_config_file(DEFAULT_CONFIG)
        print("[*] บันทึกค่าเริ่มต้น (Factory/Manual Default) เรียบร้อย")

    # 4. Start Streaming
    cam.stream_on()

    print("\n" + "="*50)
    print(" [SyncroDev Camera Control UI - Version 1.1] ")
    print("  W / S : ปรับ Exposure (สว่าง/มืด) [+/- 5000]")
    print("  A / D : ปรับ Gain (เร่งแสง/ลดนอยส์) [+/- 1]")
    print("  B     : แก้ภาพเขียว (Auto White Balance) **แนะนำ**")
    print("  Enter : บันทึกค่าปัจจุบันทับ Default")
    print("  Q     : ปิดโปรแกรม")
    print("="*50)

    try:
        while True:
            # จับภาพ Raw
            raw_image = cam.data_stream[0].get_image()
            if raw_image is None:
                continue

            # ดึงค่าปัจจุบันมาแสดงผล
            cur_exp = cam.ExposureTime.get()
            cur_gain = cam.Gain.get()

            # แปลงภาพเป็น RGB
            rgb_image = raw_image.convert("RGB")
            if rgb_image is None:
                continue

            # ดึงข้อมูลเข้า Numpy สำหรับ OpenCV
            numpy_image = rgb_image.get_numpy_array()
            if numpy_image is None:
                continue

            # แปลง RGB เป็น BGR (OpenCV Format)
            frame = cv2.cvtColor(numpy_image, cv2.COLOR_RGB2BGR)
            
            # ย่อขนาดแสดงผล (กล้อง 20MP ใหญ่เกินจอ)
            display_frame = cv2.resize(frame, (960, 640))

            # วาด UI ข้อมูลบนหน้าจอ
            cv2.putText(display_frame, f"EXP: {int(cur_exp)} | GAIN: {cur_gain:.1f}", 
                        (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
            cv2.putText(display_frame, "Press 'B' to Fix Green Tint", 
                        (20, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

            cv2.imshow("SyncroDev - MER2-2000-19U3C Tuning", display_frame)

            key = cv2.waitKey(1) & 0xFF
            
            # --- CONTROL LOGIC ---
            if key == ord('w'): # เพิ่ม Exposure
                cam.ExposureTime.set(cur_exp + 5000)
            elif key == ord('s'): # ลด Exposure
                cam.ExposureTime.set(max(20, cur_exp - 5000))
            elif key == ord('d'): # เพิ่ม Gain
                cam.Gain.set(min(24, cur_gain + 1))
            elif key == ord('a'): # ลด Gain
                cam.Gain.set(max(0, cur_gain - 1))
            elif key == ord('b'): # แก้ภาพเขียว (Auto White Balance)
                if cam.BalanceWhiteAuto.is_implemented():
                    cam.BalanceWhiteAuto.set(gx.GxAutoEntry.ONCE)
                    print("[*] ปรับสมดุลสีขาวสำเร็จ (White Balance Adjusted)")
            elif key == 13: # Enter เพื่อเซฟค่า
                cam.export_config_file(DEFAULT_CONFIG)
                print(f"[!] บันทึกค่าใหม่ลง {DEFAULT_CONFIG} สำเร็จ")
            elif key == ord('q'):
                break
                
    except Exception as e:
        print(f"[!] เกิดข้อผิดพลาด: {e}")
    finally:
        # ปิดกล้องและล้าง Resource
        cam.stream_off()
        cam.close_device()
        cv2.destroyAllWindows()
        print("[*] ปิดระบบเรียบร้อย")

if __name__ == "__main__":
    main()