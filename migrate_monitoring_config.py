import json
from pathlib import Path
from copy import deepcopy

def migrate_monitoring_config():
    file_path = Path("data/token_registry.json")
    backup_path = file_path.with_suffix(".json.bak")
    
    if file_path.exists():
        backup_path.write_bytes(file_path.read_bytes())
        print(f"✅ Бэкап создан: {backup_path}")
    else:
        print("❌ Файл token_registry.json не найден!")
        return
    
    data = json.loads(file_path.read_text(encoding="utf-8"))
    
    fixed_count = 0
    exchanges = ["Binance", "Bybit", "OKX"]
    default_ex = {"enabled": False, "spot_pairs": [], "futures_pairs": []}
    
    for entry in data:
        if entry.get("type") != "monitoring_config":
            continue
            
        config = entry.setdefault("config", {})
        
        for ex in exchanges:
            if ex not in config:
                config[ex] = deepcopy(default_ex)
                fixed_count += 1
                print(f"   → Добавлена полная секция для {ex} у токена {entry['token']}")
            else:
                ex_config = config[ex]
                if "enabled" not in ex_config:
                    ex_config["enabled"] = False
                    fixed_count += 1
                    print(f"   → Добавлен 'enabled' для {ex} у токена {entry['token']}")
        
        # === НОВОЕ: добавляем monitoring_enabled ===
        if "monitoring_enabled" not in config:
            config["monitoring_enabled"] = False
            fixed_count += 1
            print(f"   → Добавлен 'monitoring_enabled' для токена {entry['token']}")
        # ===========================================
    
    file_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    
    print(f"\n🎉 Миграция завершена! Исправлено записей: {fixed_count}")
    print("   Файл data/token_registry.json обновлён.")

if __name__ == "__main__":
    migrate_monitoring_config()