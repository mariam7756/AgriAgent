from typing import Dict, List, Optional, Tuple


AGRI_ONTOLOGY: Dict[str, Dict] = {
    "wheat": {
        "ar_names": ["قمح", "القمح"],
        "season": ["winter"], "egypt_regions": ["delta", "upper_egypt", "all"],
        "diseases": ["rust", "blight", "smut", "powdery_mildew"],
        "pests": ["aphid", "armyworm", "sunn_pest"],
        "fertilization": {
            "pre_planting": {"name": "سوبر فوسفات", "dose_kg_feddan": 150},
            "tillering":    {"name": "يوريا",        "dose_kg_feddan": 75},
            "jointing":     {"name": "يوريا",        "dose_kg_feddan": 75},
        },
        "irrigation_days": 15, "planting_months": [10, 11, 12], "harvest_months": [4, 5],
    },
    "tomato": {
        "ar_names": ["طماطم", "الطماطم", "بندورة"],
        "season": ["summer", "winter", "autumn"], "egypt_regions": ["all"],
        "diseases": ["early_blight", "late_blight", "fusarium", "leaf_curl_virus"],
        "pests": ["whitefly", "aphid", "spider_mite", "leaf_miner"],
        "fertilization": {
            "pre_planting": {"name": "سوبر فوسفات",    "dose_kg_feddan": 100},
            "vegetative":   {"name": "يوريا",           "dose_kg_feddan": 15},
            "fruiting":     {"name": "نترات بوتاسيوم",  "dose_kg_feddan": 10},
        },
        "irrigation_days": 5, "planting_months": [9, 10, 2, 3],
    },
    "corn": {
        "ar_names": ["ذرة", "الذرة", "ذرة شامية"],
        "season": ["summer"], "egypt_regions": ["all"],
        "diseases": ["gray_leaf_spot", "northern_blight", "stalk_rot"],
        "pests": ["corn_borer", "armyworm", "aphid"],
        "fertilization": {
            "pre_planting": {"name": "سوبر فوسفات", "dose_kg_feddan": 100},
            "week_3":       {"name": "يوريا",        "dose_kg_feddan": 50},
            "week_6":       {"name": "يوريا",        "dose_kg_feddan": 50},
        },
        "irrigation_days": 7, "planting_months": [3, 4, 5],
    },
    "cotton": {
        "ar_names": ["قطن", "القطن"],
        "season": ["summer"], "egypt_regions": ["delta", "middle_egypt"],
        "diseases": ["fusarium_wilt", "bacterial_blight", "boll_rot"],
        "pests": ["bollworm", "whitefly", "thrips", "spider_mite"],
        "fertilization": {
            "pre_planting": {"name": "سوبر فوسفات",    "dose_kg_feddan": 100},
            "vegetative":   {"name": "يوريا",           "dose_kg_feddan": 45},
            "boll_setting": {"name": "نترات بوتاسيوم",  "dose_kg_feddan": 25},
        },
        "irrigation_days": 10, "planting_months": [3, 4],
    },
    "rice": {
        "ar_names": ["أرز", "الأرز"],
        "season": ["summer"], "egypt_regions": ["delta"],
        "diseases": ["blast", "sheath_blight", "bacterial_leaf_blight"],
        "pests": ["stem_borer", "brown_planthopper"],
        "fertilization": {
            "pre_planting": {"name": "سوبر فوسفات", "dose_kg_feddan": 100},
            "tillering":    {"name": "يوريا",        "dose_kg_feddan": 45},
            "panicle":      {"name": "يوريا",        "dose_kg_feddan": 30},
        },
        "irrigation_days": 3, "planting_months": [5, 6],
    },
    "potato": {
        "ar_names": ["بطاطس", "البطاطس", "بطاطا"],
        "season": ["winter", "summer"], "egypt_regions": ["all"],
        "diseases": ["late_blight", "early_blight", "scab", "blackleg"],
        "pests": ["aphid", "potato_tuber_moth", "wireworm"],
        "fertilization": {
            "pre_planting": {"name": "سوبر فوسفات",      "dose_kg_feddan": 150},
            "vegetative":   {"name": "يوريا",             "dose_kg_feddan": 40},
            "tuber_set":    {"name": "كبريتات بوتاسيوم",  "dose_kg_feddan": 50},
        },
        "irrigation_days": 6, "planting_months": [9, 10, 11, 1, 2],
    },
    "onion": {
        "ar_names": ["بصل", "البصل"],
        "season": ["winter"], "egypt_regions": ["all"],
        "diseases": ["purple_blotch", "downy_mildew", "fusarium"],
        "pests": ["thrips", "onion_fly"],
        "fertilization": {
            "pre_planting": {"name": "سوبر فوسفات",      "dose_kg_feddan": 100},
            "vegetative":   {"name": "يوريا",             "dose_kg_feddan": 30},
            "bulbing":      {"name": "كبريتات بوتاسيوم",  "dose_kg_feddan": 30},
        },
        "irrigation_days": 10, "planting_months": [9, 10, 11],
    },
    "pepper": {
        "ar_names": ["فلفل", "الفلفل", "فلفل رومي"],
        "season": ["summer", "winter"], "egypt_regions": ["all"],
        "diseases": ["phytophthora", "bacterial_spot", "cucumber_mosaic"],
        "pests": ["aphid", "whitefly", "thrips", "spider_mite"],
        "fertilization": {
            "pre_planting": {"name": "سوبر فوسفات",    "dose_kg_feddan": 100},
            "vegetative":   {"name": "يوريا",           "dose_kg_feddan": 20},
            "fruiting":     {"name": "نترات بوتاسيوم",  "dose_kg_feddan": 15},
        },
        "irrigation_days": 5, "planting_months": [2, 3, 8, 9],
    },
    "olive": {
        "ar_names": ["زيتون", "الزيتون"],
        "season": ["perennial"], "egypt_regions": ["sinai", "north_coast", "upper_egypt"],
        "diseases": ["peacock_spot", "verticillium", "olive_knot"],
        "pests": ["olive_fly", "scale_insect", "olive_moth"],
        "fertilization": {
            "early_spring": {"name": "يوريا",             "dose_kg_feddan": 30},
            "post_harvest": {"name": "سوبر فوسفات",       "dose_kg_feddan": 50},
            "summer":       {"name": "كبريتات بوتاسيوم",  "dose_kg_feddan": 20},
        },
        "irrigation_days": 20, "planting_months": [2, 3],
    },
    "sugarcane": {
        "ar_names": ["قصب السكر", "القصب"],
        "season": ["summer"], "egypt_regions": ["upper_egypt"],
        "diseases": ["red_rot", "smut", "ratoon_stunting"],
        "pests": ["stem_borer", "woolly_aphid"],
        "fertilization": {
            "planting":   {"name": "سوبر فوسفات", "dose_kg_feddan": 150},
            "month_2":    {"name": "يوريا",        "dose_kg_feddan": 60},
            "month_5":    {"name": "يوريا",        "dose_kg_feddan": 60},
        },
        "irrigation_days": 10, "planting_months": [2, 3],
    },
    "mint": {
        "ar_names": ["نعناع", "النعناع"],
        "season": ["perennial", "summer"], "egypt_regions": ["all"],
        "diseases": ["powdery_mildew", "rust", "root_rot"],
        "pests": ["aphid", "spider_mite", "mint_flea_beetle"],
        "fertilization": {
            "pre_planting": {"name": "سماد عضوي (كمبوست)", "dose_kg_feddan": 2000},
            "vegetative":   {"name": "يوريا",               "dose_kg_feddan": 25},
        },
        "irrigation_days": 1, "planting_months": [3, 4, 9, 10],
    },
    "basil": {
        "ar_names": ["ريحان", "الريحان"],
        "season": ["summer"], "egypt_regions": ["all"],
        "diseases": ["fusarium_wilt", "downy_mildew", "root_rot"],
        "pests": ["aphid", "whitefly", "spider_mite"],
        "fertilization": {
            "pre_planting": {"name": "سماد عضوي (كمبوست)", "dose_kg_feddan": 1500},
            "vegetative":   {"name": "يوريا",               "dose_kg_feddan": 20},
        },
        "irrigation_days": 2, "planting_months": [3, 4, 5],
    },
}


class AgricultureOntology:
    def __init__(self):
        self._data = AGRI_ONTOLOGY

    def to_dict(self) -> Dict:
        return {
            "crops": list(self._data.keys()),
            "topics": ["cultivation", "irrigation", "fertilization", "disease_management",
                       "pest_management", "harvest", "soil_management", "general"],
            "diseases": list({d for c in self._data.values() for d in c.get("diseases", [])}),
            "pests":    list({p for c in self._data.values() for p in c.get("pests", [])}),
        }

    def get_crop(self, crop_key: str) -> Optional[Dict]:
        return self._data.get(crop_key)


class FAQDataset:
    def __init__(self):
        self.faq = [
            {"question": "كيف أزرع الزيتون؟", "intent": "cultivation", "crop": "olive",
             "answer_template": "اختر تربة جيدة الصرف ومكان مشمس. ابدأ الزراعة فبراير-مارس."},
            {"question": "ورق الزيتون أصفر", "intent": "diagnosis", "crop": "olive",
             "answer_template": "راجع انتظام الري وافحص نقص العناصر أو الإصابة المرضية."},
        ]

    def list_items(self) -> List[Dict]:
        return self.faq


def get_crop_by_arabic_name(name: str) -> Tuple[Optional[str], Optional[Dict]]:
    name_lower = (name or "").strip()
    for crop_key, data in AGRI_ONTOLOGY.items():
        if name_lower in data.get("ar_names", []) or name_lower == crop_key:
            return crop_key, data
    return None, None


def get_fertilization_plan(crop_key: str, area_feddan: float = 1.0) -> Dict:
    crop = AGRI_ONTOLOGY.get(crop_key)
    if not crop:
        return {}
    return {
        "crop": crop_key,
        "ar_name": crop["ar_names"][0] if crop.get("ar_names") else crop_key,
        "area_feddan": area_feddan,
        "stages": [
            {
                "stage": stage,
                "fertilizer": info["name"],
                "dose_per_feddan_kg": info["dose_kg_feddan"],
                "total_kg": round(info["dose_kg_feddan"] * area_feddan, 1),
            }
            for stage, info in crop.get("fertilization", {}).items()
        ],
    }
    