from sqlalchemy import select

from app.database import SessionLocal
from app.models import City, User

CITY_SEED = [
    ("110000", "北京市", "Beijing", "北京市", 116.4074, 39.9042),
    ("440100", "广州市", "Guangzhou", "广东省", 113.2644, 23.1291),
    ("450200", "柳州市", "Liuzhou", "广西壮族自治区", 109.4281, 24.3264),
    ("440800", "湛江市", "Zhanjiang", "广东省", 110.3594, 21.2707),
    ("810000", "香港特别行政区", "Hong Kong", "香港特别行政区", 114.1694, 22.3193),
]


def seed() -> None:
    with SessionLocal.begin() as db:
        user = db.scalar(select(User).where(User.username == "AuroraRovella"))
        if user is None:
            db.add(
                User(
                    username="AuroraRovella",
                    display_name="Aurora Rovella",
                    role="first_tester",
                    is_test_user=True,
                )
            )

        existing_adcodes = set(db.scalars(select(City.adcode)).all())
        for adcode, name_zh, name_en, province_zh, longitude, latitude in CITY_SEED:
            if adcode not in existing_adcodes:
                db.add(
                    City(
                        adcode=adcode,
                        name_zh=name_zh,
                        name_en=name_en,
                        province_zh=province_zh,
                        longitude=longitude,
                        latitude=latitude,
                    )
                )

    print("Seed complete: AuroraRovella is the first tester; no trips or visits were invented.")


if __name__ == "__main__":
    seed()

