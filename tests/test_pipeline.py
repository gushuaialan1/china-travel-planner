import importlib.util
import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TPF_GENERATE_PATH = REPO_ROOT / "page-generator" / "scripts" / "tpf-generate.py"
TPF_CLI_PATH = REPO_ROOT / "page-generator" / "scripts" / "tpf-cli.py"
SEARCH_TRAVEL_INFO_PATH = REPO_ROOT / "scripts" / "search_travel_info.py"
SCHEMA_PATH = REPO_ROOT / "page-generator" / "schema" / "trip-schema.json"


def load_tpf_generate_module():
    spec = importlib.util.spec_from_file_location("tpf_generate", TPF_GENERATE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_generate_minimal():
    module = load_tpf_generate_module()
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    trip_data = module.generate_trip_data(
        {"city": "长沙", "days": 2},
        {"with_images": False, "with_metro": False},
    )

    for key in schema["required"]:
        assert key in trip_data

    assert trip_data["meta"]["title"] == "长沙 2天1晚旅行计划"
    assert trip_data["hero"]["heroImage"] == ""
    assert len(trip_data["days"]) == 2
    assert len(trip_data["hotels"]) >= 3  # minimum 3 hotel recommendations
    assert len(trip_data["attractions"]) == 1
    assert trip_data["days"][0]["hotel"] == "长沙推荐酒店"
    assert trip_data["days"][0]["attractions"] == []
    assert trip_data["days"][0]["segments"]["morning"] == ["抵达长沙，入住酒店", "自由活动或休整"]
    assert trip_data["days"][1]["hotel"] is None
    assert trip_data["days"][1]["segments"]["morning"] == ["退房整理行李"]
    assert trip_data["days"][1]["segments"]["afternoon"] == ["返程"]


def test_generate_full(monkeypatch):
    module = load_tpf_generate_module()
    queries = []

    def fake_search_images(query, limit=3):
        queries.append((query, limit))
        return f"https://img.example/{query}"

    monkeypatch.setattr(module, "search_images", fake_search_images)
    monkeypatch.setattr(
        module,
        "fetch_metro_data",
        lambda city: {"lines": [{"name": "1号线"}, {"name": "2号线"}]},
    )

    parsed = {
        "city": "长沙",
        "days": 3,
        "nights": 2,
        "attractions": ["岳麓山", "橘子洲"],
        "hotels": [
            {
                "phase": "前两晚",
                "name": "君悦酒店",
                "dateRange": "2026/04/01 - 2026/04/02",
                "station": "五一广场",
                "status": "已预订",
                "price": "¥800",
                "distanceToMetro": "步行5分钟",
                "image": "https://hotel.example/grand",
                "highlights": ["地段好", "早餐不错"],
            }
        ],
        "side_trips": [{"name": "岳阳", "date": "1天", "role": "周边侧游", "description": "看洞庭湖"}],
        "budget": 2500,
        "heroImage": "",
    }

    trip_data = module.generate_trip_data(
        parsed,
        {"with_images": True, "with_metro": True},
    )

    assert trip_data["hero"]["heroImage"] == "https://img.example/长沙 城市风景"
    assert trip_data["attractions"][0]["image"] == "https://img.example/岳麓山 长沙"
    assert trip_data["attractions"][1]["image"] == "https://img.example/橘子洲 长沙"
    assert trip_data["sideTrips"][0]["image"] == "https://img.example/岳阳 旅游"
    assert trip_data["hotels"][0]["image"] == "https://hotel.example/grand"
    assert trip_data["stats"][-1]["value"] == "约 ¥2500/人"
    assert [line["name"] for line in trip_data["metroCoverage"]["lines"]] == ["1号线", "2号线"]
    assert [day["hotel"] for day in trip_data["days"]] == ["君悦酒店", "君悦酒店", None]
    assert [len(day["attractions"]) for day in trip_data["days"]] == [1, 1, 0]
    assert trip_data["days"][0]["attractions"][0]["name"] == "岳麓山"
    assert trip_data["days"][1]["attractions"][0]["name"] == "橘子洲"
    assert trip_data["days"][0]["segments"]["morning"] == ["抵达长沙，入住酒店", "前往岳麓山"]
    assert trip_data["days"][0]["segments"]["afternoon"] == ["深度游览岳麓山"]
    assert trip_data["days"][1]["segments"]["morning"] == ["前往橘子洲"]
    assert trip_data["days"][2]["segments"]["morning"] == ["退房整理行李"]
    assert trip_data["days"][2]["segments"]["afternoon"] == ["返程"]
    assert queries == [
        ("岳麓山 长沙", 1),
        ("橘子洲 长沙", 1),
        ("岳阳 旅游", 1),
        ("长沙 城市风景", 1),
    ]


def test_side_trips_string_array():
    module = load_tpf_generate_module()

    trip_data = module.generate_trip_data(
        {
            "city": "长沙",
            "days": 2,
            "side_trips": ["岳阳", "株洲"],
        },
        {"with_images": False, "with_metro": False},
    )

    assert trip_data["sideTrips"] == [
        {
            "name": "岳阳",
            "date": "1天",
            "role": "周边侧游",
            "description": "可作为周边顺路行程",
            "image": "",
        },
        {
            "name": "株洲",
            "date": "1天",
            "role": "周边侧游",
            "description": "可作为周边顺路行程",
            "image": "",
        },
    ]


def test_side_trips_dict_old_format():
    module = load_tpf_generate_module()

    trip_data = module.generate_trip_data(
        {
            "city": "长沙",
            "days": 2,
            "side_trips": [
                {
                    "destination": "张家界",
                    "duration": "2天1晚",
                    "highlights": ["天门山", "森林公园"],
                }
            ],
        },
        {"with_images": False, "with_metro": False},
    )

    assert trip_data["sideTrips"] == [
        {
            "name": "张家界",
            "date": "2天1晚",
            "role": "周边侧游",
            "description": "天门山；森林公园",
            "image": "",
        }
    ]


def test_validate_pass(tmp_path):
    module = load_tpf_generate_module()
    trip_data = module.generate_trip_data(
        {
            "city": "长沙",
            "days": 2,
            "attractions": ["岳麓山"],
            "side_trips": ["岳阳"],
        },
        {"with_images": False, "with_metro": False},
    )

    project_dir = tmp_path / "demo-project"
    data_dir = project_dir / "data"
    data_dir.mkdir(parents=True)
    (data_dir / "trip-data.json").write_text(
        json.dumps(trip_data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(TPF_CLI_PATH), "validate"],
        cwd=project_dir,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert "Validation passed" in result.stdout


def test_search_travel_info_help():
    result = subprocess.run(
        [sys.executable, str(SEARCH_TRAVEL_INFO_PATH), "--help"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "usage:" in result.stdout.lower()
