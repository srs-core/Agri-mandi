from __future__ import annotations

import csv
import os
import re
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.db.session import SessionLocal
from app.models.entities import (
    BuyerDirectoryEntry,
    BuyerPreferredCategory,
    BuyerPreferredCommodity,
    BuyerType,
    Commodity,
    CommodityCategory,
    DataSource,
    HistoricalInfrastructureRecord,
    Location,
    LogisticsProvider,
    SourceAttribution,
    SourceType,
    SourceVerificationStatus,
)
from app.modules.ingestion.pipeline import (
    CATEGORY_ALIASES,
    COMMODITY_EXACT_ALIASES,
    DISALLOWED_DAIRY_KEYWORDS,
    DISALLOWED_NON_CROP_KEYWORDS,
    resolve_commodity_or_category,
    validate_crop_only,
)


def parse_confidence_score(conf_str: str | None) -> Decimal:
    if not conf_str:
        return Decimal("0.800")
    c = conf_str.strip().lower()
    if c == "high":
        return Decimal("0.950")
    elif c in ["medium-high", "medium high"]:
        return Decimal("0.850")
    elif c == "medium":
        return Decimal("0.700")
    elif c in ["low-medium", "low"]:
        return Decimal("0.500")
    return Decimal("0.800")


def parse_buyer_type(type_str: str | None) -> BuyerType:
    if not type_str:
        return BuyerType.WHOLESALER
    t = type_str.strip().lower()
    if "exporter" in t:
        return BuyerType.EXPORTER
    elif "processor" in t:
        return BuyerType.PROCESSOR
    elif "retail" in t:
        return BuyerType.RETAILER
    elif "commission" in t or "agent" in t:
        return BuyerType.COMMISSION_AGENT
    elif "horeca" in t or "foodservice" in t or "hotel" in t or "restaurant" in t:
        return BuyerType.HORECA
    elif "wholesaler" in t or "trader" in t or "procurement" in t or "b2b" in t:
        return BuyerType.WHOLESALER
    return BuyerType.OTHER


def parse_evidence_date(date_str: str | None) -> date | None:
    if not date_str or date_str.strip() in ["", "Unknown", "TBD", "N/A"]:
        return None
    try:
        return datetime.strptime(date_str.strip(), "%Y-%m-%d").date()
    except Exception:
        return None


def clean_phone_field(phone_raw: str | None) -> tuple[str | None, str | None]:
    if not phone_raw or phone_raw.strip() in ["", "N/A", "Not publicly stated", "Not reliably published"]:
        return None, None
    raw = phone_raw.strip()
    phones = [p.strip() for p in re.split(r"[,;/]+", raw) if p.strip()]
    if not phones:
        return None, None
    primary = phones[0][:32]
    extra_note = f"Contact phones: {raw}" if len(phones) > 1 or len(primary) != len(raw) else None
    return primary, extra_note


def clean_email_field(email_raw: str | None) -> tuple[str | None, str | None]:
    if not email_raw or email_raw.strip() in ["", "N/A", "Not publicly stated"]:
        return None, None
    raw = email_raw.strip()
    if "@" in raw:
        return raw[:320], None
    return None, f"Contact note: {raw}"


def extract_location_info(location_text: str | None, procurement_area: str | None) -> tuple[str, str | None, str, str, str | None]:
    """Extracts (name, taluka, district, state, postal_code) from unstructured location text without fabricating coordinates."""
    if not location_text or location_text.strip() == "":
        location_text = "Pune Area"

    name = location_text.strip()
    state = "Maharashtra"
    district = "Pune"
    taluka = None
    postal_code = None

    # Search for 6-digit postal code
    pincode_match = re.search(r"\b(41\d{4})\b", name)
    if pincode_match:
        postal_code = pincode_match.group(1)

    # Search for taluka in text or procurement area
    combined_text = f"{name} {procurement_area or ''}".lower()
    pune_talukas = [
        "haveli", "baramati", "junnar", "khed", "shirur", "indapur",
        "daund", "ambegaon", "purandar", "maval", "mulshi", "velhe", "bhor"
    ]
    for t in pune_talukas:
        if t in combined_text:
            taluka = t.capitalize()
            break

    if "thane" in combined_text:
        district = "Thane"
    elif "mumbai" in combined_text:
        district = "Mumbai"

    return name, taluka, district, state, postal_code


def get_or_create_text_location(db: Session, name: str, taluka: str | None, district: str, state: str, postal_code: str | None) -> Location:
    stmt = select(Location).where(
        func.lower(Location.name) == name.strip().lower(),
        Location.district == district,
        Location.state == state,
    )
    if taluka:
        stmt = stmt.where(Location.taluka == taluka)
    loc = db.scalar(stmt)
    if not loc:
        loc = Location(
            name=name.strip(),
            taluka=taluka,
            district=district,
            state=state,
            country_code="IN",
            postal_code=postal_code,
            latitude=None,  # Do NOT fabricate coordinates
            longitude=None,
            geo_point=None,
        )
        db.add(loc)
        db.flush()
    return loc


def run_phase2a_import(data_dir: str | Path | None = None) -> dict[str, Any]:
    """Executes the idempotent Phase 2A research dataset import."""
    if data_dir is None:
        # Search candidate paths
        candidates = [
            Path("/app/data/phase2a"),
            Path("data/phase2a"),
            Path("AgriMandi_Phase2A_Pune_CSV_Package/phase2a"),
            Path("/app/AgriMandi_Phase2A_Pune_CSV_Package/phase2a"),
            Path("c:/Users/Shoury/Desktop/Agri-mandi/data/phase2a"),
            Path("c:/Users/Shoury/Desktop/Agri-mandi/AgriMandi_Phase2A_Pune_CSV_Package/phase2a"),
        ]
        for c in candidates:
            if c.exists() and (c / "sources.csv").exists():
                data_dir = c
                break

    if not data_dir or not Path(data_dir).exists():
        raise FileNotFoundError(f"Could not locate Phase 2A dataset directory. Checked: {[str(c) for c in candidates]}")

    data_path = Path(data_dir)
    print(f"[Phase 2A Import] Ingesting dataset from: {data_path.resolve()}")

    db = SessionLocal()
    report: dict[str, Any] = {
        "imported_counts": {},
        "rejected_records": [],
        "historical_records": [],
        "idempotent_skips": 0,
        "final_database_counts": {},
    }

    try:
        # -------------------------------------------------------------
        # STEP 1: Ingest sources.csv ➔ data_sources
        # -------------------------------------------------------------
        sources_csv = data_path / "sources.csv"
        source_id_map: dict[str, DataSource] = {}
        sources_imported = 0

        with open(sources_csv, mode="r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                src_id = row["Source_ID"].strip()
                src_name = row["Source_Name"].strip()
                src_type_raw = row["Source_Type"].strip().lower()
                src_url = row["URL"].strip() if row.get("URL") else None
                freshness = row.get("Freshness/Date Context", "").strip()
                usage = row.get("Usage", "").strip()
                caution = row.get("Caution", "").strip()

                if "official" in src_type_raw or "directory" in src_type_raw:
                    source_type = SourceType.BUYER_RESEARCH
                elif "guideline" in src_type_raw or "report" in src_type_raw or "government" in src_type_raw:
                    source_type = SourceType.GOVERNMENT
                elif "logistics" in src_type_raw or "transport" in src_type_raw:
                    source_type = SourceType.LOGISTICS_RESEARCH
                else:
                    source_type = SourceType.BUYER_RESEARCH

                verification_status = (
                    SourceVerificationStatus.VERIFIED
                    if freshness.lower() == "current"
                    else SourceVerificationStatus.UNVERIFIED
                )

                notes = f"Usage: {usage} | Caution: {caution} | Context: {freshness}"

                ds = db.scalar(select(DataSource).where(DataSource.name == src_name))
                if not ds:
                    ds = DataSource(
                        name=src_name,
                        source_type=source_type,
                        source_url=src_url if src_url and src_url != "" else None,
                        checked_at=datetime.now(timezone.utc),
                        verification_status=verification_status,
                        confidence_score=Decimal("0.900") if verification_status == SourceVerificationStatus.VERIFIED else Decimal("0.750"),
                        is_mock=False,
                        notes=notes,
                    )
                    db.add(ds)
                    db.flush()
                    sources_imported += 1

                source_id_map[src_id] = ds
                # Also index by source_name and source_url
                source_id_map[src_name.lower()] = ds
                if src_url:
                    source_id_map[src_url.lower()] = ds

        report["imported_counts"]["data_sources"] = sources_imported
        print(f"✓ Step 1 Complete: Ingested/verified {len(source_id_map)} data source records.")

        # Default fallback data sources
        general_buyer_ds = db.scalar(select(DataSource).where(DataSource.name == "MSAMB official buyer directory"))
        if not general_buyer_ds:
            general_buyer_ds = list(source_id_map.values())[0]

        general_logistics_ds = db.scalar(select(DataSource).where(DataSource.source_type == SourceType.LOGISTICS_RESEARCH))
        if not general_logistics_ds:
            general_logistics_ds = general_buyer_ds

        # -------------------------------------------------------------
        # STEP 2: Ingest buyers.csv ➔ buyer_directory_entries
        # -------------------------------------------------------------
        buyers_csv = data_path / "buyers.csv"
        buyer_id_map: dict[str, BuyerDirectoryEntry] = {}
        buyers_imported = 0

        with open(buyers_csv, mode="r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ext_id = row["buyer_external_id"].strip()
                bname = row["business_name"].strip()
                btype = parse_buyer_type(row.get("buyer_type"))
                loc_text = row.get("location")
                proc_area = row.get("procurement_area")
                req_qty = row.get("required_quantity", "").strip()
                phone = row.get("public_phone", "").strip()
                email = row.get("public_email", "").strip()
                src_url = row.get("source_url", "").strip()
                conf_str = row.get("confidence")
                notes_text = row.get("research_status_notes")
                buyer_signal = row.get("buyer_procurement_signal", "")

                # Zero dairy verification
                validate_crop_only(bname)

                # Clean misaligned required_quantity containing phone numbers
                raw_phone = phone
                if req_qty and any(char.isdigit() for char in req_qty):
                    if ("-" in req_qty or "/" in req_qty or "+91" in req_qty) and (not raw_phone or raw_phone in ["N/A", "Not publicly stated", "Not reliably published"]):
                        raw_phone = req_qty

                daily_capacity = None
                if req_qty and ("moq" in req_qty.lower() or "mt" in req_qty.lower()):
                    num_match = re.search(r"(\d+)\s*mt", req_qty.lower())
                    if num_match:
                        daily_capacity = Decimal(num_match.group(1))

                cleaned_phone, phone_note = clean_phone_field(raw_phone)
                cleaned_email, email_note = clean_email_field(email)

                name, taluka, district, state, postal_code = extract_location_info(loc_text, proc_area)
                loc = get_or_create_text_location(db, name, taluka, district, state, postal_code)

                confidence = parse_confidence_score(conf_str)

                # Match data source
                ds = source_id_map.get(src_url.lower()) if src_url else None
                if not ds:
                    ds = general_buyer_ds

                extra_notes_parts = [notes_text, f"Signal: {buyer_signal}" if buyer_signal else None, phone_note, email_note]
                combined_notes = " | ".join([p for p in extra_notes_parts if p and p.strip() != ""])

                # Check if entry already exists
                entry = db.scalar(select(BuyerDirectoryEntry).where(BuyerDirectoryEntry.external_id == ext_id))
                if not entry:
                    entry = BuyerDirectoryEntry(
                        external_id=ext_id,
                        business_name=bname,
                        buyer_type=btype,
                        location_id=loc.id,
                        contact_person=None,
                        contact_phone=cleaned_phone,
                        contact_email=cleaned_email,
                        procurement_radius_km=None,
                        daily_capacity_mt=daily_capacity,
                        typical_payment_terms="Commercial B2B Terms" if "b2b" in (row.get("purchase_mode") or "").lower() else None,
                        notes=combined_notes if combined_notes else None,
                        is_active=True,
                    )
                    db.add(entry)
                    db.flush()

                    # Attach provenance
                    attr = SourceAttribution(
                        data_source_id=ds.id,
                        entity_type="buyer_directory_entry",
                        entity_id=entry.id,
                        external_record_id=ext_id,
                        verification_status=(
                            SourceVerificationStatus.VERIFIED if conf_str == "High" else SourceVerificationStatus.UNVERIFIED
                        ),
                        confidence_score=confidence,
                    )
                    db.add(attr)
                    buyers_imported += 1
                else:
                    report["idempotent_skips"] += 1

                buyer_id_map[ext_id] = entry

        report["imported_counts"]["buyer_directory_entries"] = buyers_imported
        print(f"✓ Step 2 Complete: Ingested/verified {len(buyer_id_map)} buyer directory entries.")

        # -------------------------------------------------------------
        # STEP 3: Ingest buyer_commodities.csv ➔ preferred_commodities / preferred_categories
        # -------------------------------------------------------------
        buyer_comms_csv = data_path / "buyer_commodities.csv"
        pref_comms_imported = 0
        pref_cats_imported = 0
        seen_commodities: set[tuple[Any, Any]] = set()
        seen_categories: set[tuple[Any, Any]] = set()

        with open(buyer_comms_csv, mode="r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                buyer_ext_id = row["buyer_external_id"].strip()
                raw_comm = row["commodity_name"].strip()

                # Rule: Check non-crop items (e.g. poultry)
                if raw_comm.lower() in DISALLOWED_NON_CROP_KEYWORDS:
                    report["rejected_records"].append({
                        "buyer_external_id": buyer_ext_id,
                        "raw_commodity": raw_comm,
                        "reason": f"Rejected non-crop/livestock item '{raw_comm}' (Strictly crops only)",
                    })
                    continue

                buyer_entry = buyer_id_map.get(buyer_ext_id)
                if not buyer_entry:
                    buyer_entry = db.scalar(select(BuyerDirectoryEntry).where(BuyerDirectoryEntry.external_id == buyer_ext_id))
                if not buyer_entry:
                    report["rejected_records"].append({
                        "buyer_external_id": buyer_ext_id,
                        "raw_commodity": raw_comm,
                        "reason": f"Unknown buyer external ID '{buyer_ext_id}'",
                    })
                    continue

                comm, cat = resolve_commodity_or_category(db, raw_comm)

                if comm:
                    comm_key = (buyer_entry.id, comm.id)
                    if comm_key not in seen_commodities:
                        seen_commodities.add(comm_key)
                        existing_p = db.scalar(
                            select(BuyerPreferredCommodity).where(
                                BuyerPreferredCommodity.buyer_entry_id == buyer_entry.id,
                                BuyerPreferredCommodity.commodity_id == comm.id,
                            )
                        )
                        if not existing_p:
                            p = BuyerPreferredCommodity(
                                buyer_entry_id=buyer_entry.id,
                                commodity_id=comm.id,
                                min_quality_grade=None,
                                typical_volume_quintals=None,
                                max_price_per_unit=None,
                            )
                            db.add(p)
                            pref_comms_imported += 1
                elif cat:
                    cat_key = (buyer_entry.id, cat)
                    if cat_key not in seen_categories:
                        seen_categories.add(cat_key)
                        existing_c = db.scalar(
                            select(BuyerPreferredCategory).where(
                                BuyerPreferredCategory.buyer_entry_id == buyer_entry.id,
                                BuyerPreferredCategory.category == cat,
                            )
                        )
                        if not existing_c:
                            c = BuyerPreferredCategory(
                                buyer_entry_id=buyer_entry.id,
                                category=cat,
                                notes=f"Broad category procurement: {raw_comm}",
                            )
                            db.add(c)
                            pref_cats_imported += 1

        report["imported_counts"]["buyer_preferred_commodities"] = pref_comms_imported
        report["imported_counts"]["buyer_preferred_categories"] = pref_cats_imported
        print(f"✓ Step 3 Complete: Ingested {pref_comms_imported} specific crop preferences and {pref_cats_imported} broad category preferences.")

        # -------------------------------------------------------------
        # STEP 4: Ingest logistics_providers.csv ➔ historical_infrastructure_records
        # -------------------------------------------------------------
        logistics_csv = data_path / "logistics_providers.csv"
        hist_infra_imported = 0

        with open(logistics_csv, mode="r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ext_id = row["logistics_external_id"].strip()
                name = row["name"].strip()
                lead_type = row["lead_type"].strip()
                sector = row["commodity_sector"].strip()
                district_area = row.get("district_area")
                state = row.get("state", "Maharashtra")
                cov_label = row.get("coverage_label")
                loc_gran = row.get("location_granularity")
                ev_type = row.get("evidence_type", "Government cold-chain project record")
                gov_status = row.get("government_project_status")
                ev_date = parse_evidence_date(row.get("evidence_date"))
                svc_status = row.get("current_service_status", "Unknown")
                ver_status = row.get("verification_status", "Historical infrastructure evidence")

                # Create location reference
                loc_name = f"{district_area or 'Pune'} Industrial Cold Project Area"
                loc = get_or_create_text_location(db, loc_name, None, district_area or "Pune", state, None)

                existing_infra = db.scalar(
                    select(HistoricalInfrastructureRecord).where(HistoricalInfrastructureRecord.external_id == ext_id)
                )
                if not existing_infra:
                    infra = HistoricalInfrastructureRecord(
                        external_id=ext_id,
                        name=name,
                        lead_type=lead_type,
                        commodity_sector=sector,
                        district_area=district_area,
                        state=state,
                        coverage_label=cov_label,
                        location_granularity=loc_gran,
                        evidence_type=ev_type,
                        government_project_status=gov_status,
                        evidence_date=ev_date,
                        current_service_status=svc_status,
                        verification_status=ver_status,
                        location_id=loc.id,
                        notes=f"Vehicles: {row.get('vehicle_info')} | Reefer: {row.get('refrigeration_info')} | Storage: {row.get('storage_info')}",
                    )
                    db.add(infra)
                    db.flush()

                    # Attach provenance
                    attr = SourceAttribution(
                        data_source_id=general_logistics_ds.id,
                        entity_type="historical_infrastructure_record",
                        entity_id=infra.id,
                        external_record_id=ext_id,
                        verification_status=SourceVerificationStatus.UNVERIFIED,
                        confidence_score=Decimal("0.850"),
                    )
                    db.add(attr)
                    hist_infra_imported += 1
                    report["historical_records"].append({
                        "external_id": ext_id,
                        "name": name,
                        "evidence_date": str(ev_date),
                        "status": ver_status,
                    })

        report["imported_counts"]["historical_infrastructure_records"] = hist_infra_imported
        print(f"✓ Step 4 Complete: Ingested {hist_infra_imported} isolated historical infrastructure evidence records.")

        db.commit()
        print("✓ All transactions committed successfully.")

        # -------------------------------------------------------------
        # STEP 5: Verify Final Database Counts
        # -------------------------------------------------------------
        report["final_database_counts"] = {
            "data_sources": db.scalar(select(func.count(DataSource.id))),
            "buyer_directory_entries": db.scalar(select(func.count(BuyerDirectoryEntry.id))),
            "buyer_preferred_commodities": db.scalar(select(func.count(BuyerPreferredCommodity.id))),
            "buyer_preferred_categories": db.scalar(select(func.count(BuyerPreferredCategory.id))),
            "historical_infrastructure_records": db.scalar(select(func.count(HistoricalInfrastructureRecord.id))),
            "active_logistics_providers": db.scalar(select(func.count(LogisticsProvider.id))),
            "source_attributions": db.scalar(select(func.count(SourceAttribution.id))),
        }

    except Exception as exc:
        db.rollback()
        raise exc
    finally:
        db.close()

    return report


if __name__ == "__main__":
    report = run_phase2a_import()
    import json
    print("\n" + "=" * 80)
    print("PHASE 2A IMPORT EXECUTION REPORT")
    print("=" * 80)
    print(json.dumps(report, indent=2, default=str))
