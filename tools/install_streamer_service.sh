#!/bin/bash
# ============================================================
# YANSHEE MJPEG STREAMER — AUTO-START SERVICE INSTALLER
# Script này cài đặt service tự khởi động camera stream
# mỗi khi robot Yanshee bật nguồn.
#
# Cách dùng: SSH vào robot rồi chạy:
#   bash install_streamer_service.sh
# ============================================================

set -e

SCRIPT_PATH="/home/pi/yanshee_mjpeg_streamer.py"
SERVICE_NAME="yanshee-camera"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

echo ""
echo "============================================================"
echo "  YANSHEE CAMERA STREAMER - SERVICE INSTALLER"
echo "============================================================"

# Kiem tra file streamer ton tai
if [ ! -f "$SCRIPT_PATH" ]; then
    echo "[FAILED] Khong tim thay file: $SCRIPT_PATH"
    echo "Hay tao file truoc bang lenh: nano $SCRIPT_PATH"
    exit 1
fi

echo "[OK] Tim thay streamer script: $SCRIPT_PATH"

# Tao systemd service file
echo "[...] Dang tao systemd service..."

sudo bash -c "cat > $SERVICE_FILE" << EOF
[Unit]
Description=Yanshee MJPEG Camera Streamer
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi
ExecStart=/usr/bin/python3 /home/pi/yanshee_mjpeg_streamer.py
Restart=always
RestartSec=3
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

echo "[OK] Service file da duoc tao: $SERVICE_FILE"

# Reload systemd, enable va start service
echo "[...] Dang kich hoat service..."
sudo systemctl daemon-reload
sudo systemctl enable ${SERVICE_NAME}.service
sudo systemctl start ${SERVICE_NAME}.service

# Kiem tra trang thai
sleep 2
STATUS=$(sudo systemctl is-active ${SERVICE_NAME}.service)

echo ""
echo "============================================================"
if [ "$STATUS" = "active" ]; then
    echo "  [OK] Service '${SERVICE_NAME}' da duoc cai dat va dang chay!"
    echo ""
    echo "  Stream URL: http://$(hostname -I | awk '{print $1}'):8000/stream.mjpg"
    echo ""
    echo "  Cac lenh huu ich:"
    echo "    Xem trang thai : sudo systemctl status ${SERVICE_NAME}"
    echo "    Xem log        : sudo journalctl -u ${SERVICE_NAME} -f"
    echo "    Dung service   : sudo systemctl stop ${SERVICE_NAME}"
    echo "    Tat auto-start : sudo systemctl disable ${SERVICE_NAME}"
    echo "    Khoi dong lai  : sudo systemctl restart ${SERVICE_NAME}"
else
    echo "  [FAILED] Service khong khoi dong duoc."
    echo "  Chay lenh sau de xem loi:"
    echo "    sudo journalctl -u ${SERVICE_NAME} -n 20"
fi
echo "============================================================"
echo ""
