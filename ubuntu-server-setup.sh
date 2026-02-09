cat > ubuntu-server-setup.sh << 'EOF'
#!/bin/bash
# Автоматическая настройка WireGuard на Ubuntu 24.04
# Сервер: 72.56.91.172

set -e

echo "=== Установка WireGuard на Ubuntu 24.04 ==="
echo "Сервер: 72.56.91.172"
echo ""

# Обновление системы
echo "[1/8] Обновление системы..."
apt update && apt upgrade -y

# Установка WireGuard
echo "[2/8] Установка WireGuard..."
apt install wireguard wireguard-tools -y

# Создание директории и генерация ключей
echo "[3/8] Генерация ключей..."
cd /etc/wireguard
umask 077

# Генерация ключей сервера
wg genkey | tee server_private.key | wg pubkey > server_public.key

# Генерация ключей клиента (MikroTik)
wg genkey | tee client_private.key | wg pubkey > client_public.key

echo ""
echo "=========================================="
echo "СОХРАНИТЕ ЭТИ КЛЮЧИ В БЕЗОПАСНОМ МЕСТЕ!"
echo "=========================================="
echo ""
echo "Server Private Key:"
cat server_private.key
echo ""
echo "Server Public Key:"
cat server_public.key
echo ""
echo "Client Private Key (для MikroTik):"
cat client_private.key
echo ""
echo "Client Public Key:"
cat client_public.key
echo ""
echo "=========================================="
echo ""

# Определение сетевого интерфейса
INTERFACE=$(ip route | grep default | awk '{print $5}' | head -n1)
echo "[4/8] Обнаружен сетевой интерфейс: $INTERFACE"

# Чтение ключей
SERVER_PRIVATE_KEY=$(cat server_private.key)
CLIENT_PUBLIC_KEY=$(cat client_public.key)

# Создание конфигурации WireGuard
echo "[5/8] Создание конфигурации WireGuard..."
cat > /etc/wireguard/wg0.conf <<EOC
[Interface]
Address = 10.200.200.1/24
ListenPort = 51820
PrivateKey = $SERVER_PRIVATE_KEY

# Включаем IP forwarding
PostUp = sysctl -w net.ipv4.ip_forward=1
PostUp = iptables -A FORWARD -i wg0 -j ACCEPT
PostUp = iptables -t nat -A POSTROUTING -o $INTERFACE -j MASQUERADE

PostDown = iptables -D FORWARD -i wg0 -j ACCEPT
PostDown = iptables -t nat -D POSTROUTING -o $INTERFACE -j MASQUERADE

[Peer]
# MikroTik Router
PublicKey = $CLIENT_PUBLIC_KEY
AllowedIPs = 10.200.200.2/32
PersistentKeepalive = 25
EOC

# Включение IP forwarding
echo "[6/8] Включение IP forwarding..."
echo "net.ipv4.ip_forward=1" >> /etc/sysctl.conf
sysctl -p

# Настройка файрвола
echo "[7/8] Настройка UFW..."
ufw allow 51820/udp comment "WireGuard"
ufw allow 22/tcp comment "SSH"
echo "y" | ufw enable

# Запуск WireGuard
echo "[8/8] Запуск WireGuard..."
systemctl enable wg-quick@wg0
systemctl start wg-quick@wg0

echo ""
echo "=========================================="
echo "✅ WireGuard успешно установлен и запущен!"
echo "=========================================="
echo ""
echo "Проверка статуса:"
systemctl status wg-quick@wg0 --no-pager
echo ""
wg show
echo ""
echo "=========================================="
echo "СЛЕДУЮЩИЙ ШАГ: Настройка MikroTik"
echo "=========================================="
echo ""
echo "Используйте Client Private Key для настройки MikroTik"
echo "Используйте Server Public Key для добавления peer на MikroTik"
echo ""
EOF

chmod +x ubuntu-server-setup.sh
bash ubuntu-server-setup.sh
