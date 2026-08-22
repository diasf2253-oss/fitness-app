"""
Apple Health export.xml history backfill.

The Health app's "Export All Health Data" produces export.zip containing
export.xml — every Record ever written (often hundreds of MB). This module
stream-parses it and feeds the shared :class:`~app.health_ingest.HealthAggregator`,
so a one-time history import lands through the exact same validated pipeline
(units, timezone/night attribution, multi-source dedup, manual-precedence)
as the live daily syncs — see ``health_ingest`` for the rules.
"""
import logging
import zipfile
from typing import BinaryIO
from xml.etree import ElementTree as ET

from sqlalchemy.orm import Session as DBSession

from app.health_ingest import HealthAggregator, parse_when
from app.health_metrics import XML_DIETARY, convert_amount

logger = logging.getLogger(__name__)

STEP_TYPE = "HKQuantityTypeIdentifierStepCount"
WEIGHT_TYPE = "HKQuantityTypeIdentifierBodyMass"
SLEEP_TYPE = "HKCategoryTypeIdentifierSleepAnalysis"


def import_export_file(fileobj: BinaryIO, filename: str, db: DBSession) -> dict:
    """Parse an export.zip / export.xml stream and upsert daily rows."""
    if filename.lower().endswith(".zip") or zipfile.is_zipfile(fileobj):
        fileobj.seek(0)
        zf = zipfile.ZipFile(fileobj)
        xml_names = [n for n in zf.namelist() if n.endswith("export.xml")]
        if not xml_names:
            return {"status": "error", "detail": "No export.xml found inside the zip."}
        stream: BinaryIO = zf.open(xml_names[0])
    else:
        fileobj.seek(0)
        stream = fileobj

    agg = HealthAggregator()

    context = ET.iterparse(stream, events=("start", "end"))
    _, root = next(context)  # grab the root so we can clear processed children

    for event, elem in context:
        if event != "end" or elem.tag != "Record":
            continue
        agg.records_seen += 1
        rtype = elem.get("type", "")
        try:
            source = elem.get("sourceName", "unknown")

            if rtype == STEP_TYPE:
                start = parse_when(elem.get("startDate"))
                agg.add_steps(start.date(), float(elem.get("value", 0)), source)

            elif rtype == WEIGHT_TYPE:
                start = parse_when(elem.get("startDate"))
                agg.add_weight(start, float(elem.get("value", 0)), elem.get("unit"), source)

            elif rtype == SLEEP_TYPE:
                start = parse_when(elem.get("startDate"))
                end = parse_when(elem.get("endDate"))
                agg.add_sleep_interval(start, end, elem.get("value", ""), source)

            elif rtype in XML_DIETARY:
                key = XML_DIETARY[rtype]
                start = parse_when(elem.get("startDate"))
                amount = convert_amount(float(elem.get("value", 0)), elem.get("unit", ""), key)
                if amount is None:
                    agg.warn(f"{rtype}: unknown unit {elem.get('unit')!r}, skipped")
                else:
                    agg.add_diet(start.date(), amount, key, source)

            elif rtype:
                agg.ignored_types.add(rtype)

        except Exception as e:
            agg.warn(f"{rtype}: {e}")
        finally:
            elem.clear()
            root.clear()

    return agg.finalize(db)
