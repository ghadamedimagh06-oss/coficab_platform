"""
Data Routes for CofICab Platform
API endpoints for retrieving livraison and ingestion data
"""

from fastapi import APIRouter, Query, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional, List
import datetime
from app.database import get_db_optional
from app.models.livraison import Livraison
from app.models.ingestion_log import IngestionLog
from app.services.ingestion_service import IngestionService

router = APIRouter()

MOCK_TRANSPORTS = [
    # Monday
    {"id": 1,  "row_number": 1,  "delivery_day": "Monday",    "client": "AEC WIRING TECHNOLOGY SARL",        "driver": "Ali Ben Salah",      "vehicle": "TU-201-AA", "start_location": "COFICAB Mégrine", "end_location": "MGHIRA",          "distance_km": 12.0,  "etd": "07:00", "eta": "07:45", "quantity": 150, "status": "completed",  "priority": "normal", "notes": None},
    {"id": 2,  "row_number": 2,  "delivery_day": "Monday",    "client": "COFAT TUNIS",                       "driver": "Mehdi Chaabane",     "vehicle": "TU-305-BB", "start_location": "COFICAB Mégrine", "end_location": "TN",              "distance_km": 1.0,   "etd": "07:30", "eta": "07:40", "quantity": 80,  "status": "completed",  "priority": "normal", "notes": None},
    {"id": 3,  "row_number": 3,  "delivery_day": "Monday",    "client": "APTIV Services Tunisia SARL",       "driver": "Khalil Mansouri",    "vehicle": "TU-412-CC", "start_location": "COFICAB Mégrine", "end_location": "MJEZ EL BEB",     "distance_km": 56.0,  "etd": "08:00", "eta": "09:30", "quantity": 200, "status": "in_transit", "priority": "high",   "notes": None},
    {"id": 4,  "row_number": 4,  "delivery_day": "Monday",    "client": "CABLISYS Tunisie",                  "driver": "Nizar Trabelsi",     "vehicle": "TU-518-DD", "start_location": "COFICAB Mégrine", "end_location": "SOUSSE",          "distance_km": 144.0, "etd": "06:30", "eta": "09:00", "quantity": 320, "status": "in_transit", "priority": "high",   "notes": "Priority route"},
    {"id": 5,  "row_number": 5,  "delivery_day": "Monday",    "client": "ERA CONTACTS TUNISIA",              "driver": "Sami Hamdi",         "vehicle": "TU-624-EE", "start_location": "COFICAB Mégrine", "end_location": "BIZERTE",         "distance_km": 60.7,  "etd": "08:30", "eta": "10:15", "quantity": 110, "status": "pending",    "priority": "normal", "notes": None},
    {"id": 6,  "row_number": 6,  "delivery_day": "Monday",    "client": "SCHULTE AUTOMOTIVE TUNISIA srl",   "driver": "Riadh Bouzid",       "vehicle": "TU-731-FF", "start_location": "COFICAB Mégrine", "end_location": "BOUARADA",        "distance_km": 90.0,  "etd": "09:00", "eta": "11:30", "quantity": 95,  "status": "pending",    "priority": "normal", "notes": None},
    # Tuesday
    {"id": 7,  "row_number": 1,  "delivery_day": "Tuesday",   "client": "LEONI SOUSSE",                      "driver": "Bilel Ayari",        "vehicle": "TU-201-AA", "start_location": "COFICAB Mégrine", "end_location": "SOUSSE",          "distance_km": 161.0, "etd": "06:00", "eta": "09:00", "quantity": 400, "status": "completed",  "priority": "urgent", "notes": "Urgent shipment"},
    {"id": 8,  "row_number": 2,  "delivery_day": "Tuesday",   "client": "LEONI MENZEL HAYET",                "driver": "Hatem Khelifi",      "vehicle": "TU-305-BB", "start_location": "COFICAB Mégrine", "end_location": "MANZEL HAYET",    "distance_km": 186.0, "etd": "05:30", "eta": "09:00", "quantity": 280, "status": "in_transit", "priority": "high",   "notes": None},
    {"id": 9,  "row_number": 3,  "delivery_day": "Tuesday",   "client": "KAB-LEM Tunisia SARL",              "driver": "Anis Dhahbi",        "vehicle": "TU-412-CC", "start_location": "COFICAB Mégrine", "end_location": "BIZERTE",         "distance_km": 64.7,  "etd": "08:00", "eta": "09:45", "quantity": 120, "status": "in_transit", "priority": "normal", "notes": None},
    {"id": 10, "row_number": 4,  "delivery_day": "Tuesday",   "client": "ELECTROCONTACT TUNISIE",            "driver": "Faouzi Slim",        "vehicle": "TU-518-DD", "start_location": "COFICAB Mégrine", "end_location": "KSAR HLEL",       "distance_km": 195.0, "etd": "05:00", "eta": "09:30", "quantity": 260, "status": "pending",    "priority": "high",   "notes": None},
    {"id": 11, "row_number": 5,  "delivery_day": "Tuesday",   "client": "Reflexallen",                       "driver": "Walid Ben Amor",     "vehicle": "TU-624-EE", "start_location": "COFICAB Mégrine", "end_location": "HAMMEM ZRIBA",    "distance_km": 59.0,  "etd": "09:00", "eta": "10:30", "quantity": 75,  "status": "pending",    "priority": "normal", "notes": None},
    # Wednesday
    {"id": 12, "row_number": 1,  "delivery_day": "Wednesday", "client": "Kromberg & Schubert Tunisie SARL",  "driver": "Maher Jlassi",       "vehicle": "TU-201-AA", "start_location": "COFICAB Mégrine", "end_location": "BEJA",            "distance_km": 104.0, "etd": "07:00", "eta": "09:45", "quantity": 180, "status": "completed",  "priority": "normal", "notes": None},
    {"id": 13, "row_number": 2,  "delivery_day": "Wednesday", "client": "SEBN",                              "driver": "Lotfi Chebbi",       "vehicle": "TU-305-BB", "start_location": "COFICAB Mégrine", "end_location": "JENDOUBA",        "distance_km": 146.0, "etd": "06:00", "eta": "09:30", "quantity": 210, "status": "in_transit", "priority": "high",   "notes": None},
    {"id": 14, "row_number": 3,  "delivery_day": "Wednesday", "client": "DIS Draxlmaier",                    "driver": "Kamel Oueslati",     "vehicle": "TU-412-CC", "start_location": "COFICAB Mégrine", "end_location": "SELIANA",         "distance_km": 126.0, "etd": "06:30", "eta": "10:00", "quantity": 160, "status": "in_transit", "priority": "normal", "notes": None},
    {"id": 15, "row_number": 4,  "delivery_day": "Wednesday", "client": "SE BORDNETZE EL FEJJA S.A.R.L",    "driver": "Tarek Bejaoui",      "vehicle": "TU-518-DD", "start_location": "COFICAB Mégrine", "end_location": "Fejja",           "distance_km": 23.4,  "etd": "10:00", "eta": "10:45", "quantity": 90,  "status": "pending",    "priority": "normal", "notes": None},
    {"id": 16, "row_number": 5,  "delivery_day": "Wednesday", "client": "AMPHENOL TUNISIE",                  "driver": "Fares Saidi",        "vehicle": "TU-624-EE", "start_location": "COFICAB Mégrine", "end_location": "FAHS",            "distance_km": 51.0,  "etd": "09:30", "eta": "11:00", "quantity": 130, "status": "pending",    "priority": "normal", "notes": None},
    # Thursday
    {"id": 17, "row_number": 1,  "delivery_day": "Thursday",  "client": "YAZAKI GAFSA",                      "driver": "Ridha Fenniche",     "vehicle": "TU-201-AA", "start_location": "COFICAB Mégrine", "end_location": "GAFSSA",          "distance_km": 336.0, "etd": "04:00", "eta": "10:30", "quantity": 500, "status": "in_transit", "priority": "urgent", "notes": "Long haul — check fuel"},
    {"id": 18, "row_number": 2,  "delivery_day": "Thursday",  "client": "YURA CORPORATION TUNISIA",          "driver": "Sofiene Hammami",    "vehicle": "TU-305-BB", "start_location": "COFICAB Mégrine", "end_location": "KAIRAOUEN",       "distance_km": 170.0, "etd": "05:30", "eta": "09:30", "quantity": 340, "status": "in_transit", "priority": "high",   "notes": None},
    {"id": 19, "row_number": 3,  "delivery_day": "Thursday",  "client": "SEWS TN SARL",                      "driver": "Mourad Gharbi",      "vehicle": "TU-412-CC", "start_location": "COFICAB Mégrine", "end_location": "MOUNASTIR",       "distance_km": 195.0, "etd": "05:00", "eta": "09:00", "quantity": 290, "status": "pending",    "priority": "high",   "notes": None},
    {"id": 20, "row_number": 4,  "delivery_day": "Thursday",  "client": "WeWire Hammamet Tunisia SARL",      "driver": "Imed Ferchichi",     "vehicle": "TU-518-DD", "start_location": "COFICAB Mégrine", "end_location": "HAMMMET",         "distance_km": 74.0,  "etd": "09:00", "eta": "11:00", "quantity": 115, "status": "pending",    "priority": "normal", "notes": None},
    # Friday
    {"id": 21, "row_number": 1,  "delivery_day": "Friday",    "client": "COELEC TUNISIA",                    "driver": "Ali Ben Salah",      "vehicle": "TU-201-AA", "start_location": "COFICAB Mégrine", "end_location": "AGBA",            "distance_km": 10.0,  "etd": "07:30", "eta": "08:00", "quantity": 60,  "status": "completed",  "priority": "normal", "notes": None},
    {"id": 22, "row_number": 2,  "delivery_day": "Friday",    "client": "COFAT MATEUR",                      "driver": "Mehdi Chaabane",     "vehicle": "TU-305-BB", "start_location": "COFICAB Mégrine", "end_location": "MATEUR",          "distance_km": 65.5,  "etd": "08:00", "eta": "09:45", "quantity": 175, "status": "completed",  "priority": "normal", "notes": None},
    {"id": 23, "row_number": 3,  "delivery_day": "Friday",    "client": "LECTRIC",                           "driver": "Khalil Mansouri",    "vehicle": "TU-412-CC", "start_location": "COFICAB Mégrine", "end_location": "FAHS",            "distance_km": 51.0,  "etd": "09:00", "eta": "10:30", "quantity": 140, "status": "in_transit", "priority": "normal", "notes": None},
    {"id": 24, "row_number": 4,  "delivery_day": "Friday",    "client": "PROD-ELEC",                         "driver": "Nizar Trabelsi",     "vehicle": "TU-518-DD", "start_location": "COFICAB Mégrine", "end_location": "KAALA KOBRA",     "distance_km": 160.0, "etd": "06:00", "eta": "09:30", "quantity": 220, "status": "in_transit", "priority": "high",   "notes": None},
    {"id": 25, "row_number": 5,  "delivery_day": "Friday",    "client": "TTE International",                 "driver": "Sami Hamdi",         "vehicle": "TU-624-EE", "start_location": "COFICAB Mégrine", "end_location": "BIZERTE",         "distance_km": 65.0,  "etd": "09:30", "eta": "11:15", "quantity": 95,  "status": "pending",    "priority": "normal", "notes": None},
    # Saturday
    {"id": 26, "row_number": 1,  "delivery_day": "Saturday",  "client": "A C T Assemblage Cable Tunisie",    "driver": "Riadh Bouzid",       "vehicle": "TU-201-AA", "start_location": "COFICAB Mégrine", "end_location": "Slimane",         "distance_km": 42.0,  "etd": "08:00", "eta": "09:15", "quantity": 85,  "status": "completed",  "priority": "normal", "notes": None},
    {"id": 27, "row_number": 2,  "delivery_day": "Saturday",  "client": "Jetty",                             "driver": "Bilel Ayari",        "vehicle": "TU-305-BB", "start_location": "COFICAB Mégrine", "end_location": "Hammem lif",      "distance_km": 30.4,  "etd": "09:00", "eta": "10:00", "quantity": 50,  "status": "in_transit", "priority": "normal", "notes": None},
    {"id": 28, "row_number": 3,  "delivery_day": "Saturday",  "client": "Perplastic TN",                     "driver": "Hatem Khelifi",      "vehicle": "TU-412-CC", "start_location": "COFICAB Mégrine", "end_location": "Mghira",          "distance_km": 9.7,   "etd": "10:00", "eta": "10:30", "quantity": 40,  "status": "pending",    "priority": "low",    "notes": None},
    # Sunday
    {"id": 29, "row_number": 1,  "delivery_day": "Sunday",    "client": "COFICAB MED",                       "driver": "Ali Ben Salah",      "vehicle": "TU-201-AA", "start_location": "COFICAB Mégrine", "end_location": "MJEZ EL BEB",     "distance_km": 56.0,  "etd": "07:00", "eta": "08:30", "quantity": 190, "status": "completed",  "priority": "high",   "notes": None},
    {"id": 30, "row_number": 2,  "delivery_day": "Sunday",    "client": "MEDITERRANEAN ELECTRIC WIRING",     "driver": "Mehdi Chaabane",     "vehicle": "TU-305-BB", "start_location": "COFICAB Mégrine", "end_location": "NADOUR",          "distance_km": 90.0,  "etd": "07:30", "eta": "09:30", "quantity": 215, "status": "completed",  "priority": "normal", "notes": None},
    {"id": 31, "row_number": 3,  "delivery_day": "Sunday",    "client": "Yazaki Automotive Products Tunisia", "driver": "Khalil Mansouri",    "vehicle": "TU-412-CC", "start_location": "COFICAB Mégrine", "end_location": "BIZERTE",         "distance_km": 65.0,  "etd": "08:00", "eta": "09:45", "quantity": 300, "status": "in_transit", "priority": "high",   "notes": None},
    {"id": 32, "row_number": 4,  "delivery_day": "Sunday",    "client": "SCHULTE AUTOMOTIVE TUN ZAGHOUAN",   "driver": "Nizar Trabelsi",     "vehicle": "TU-518-DD", "start_location": "COFICAB Mégrine", "end_location": "ZAGHOUEN",        "distance_km": 27.0,  "etd": "09:00", "eta": "10:00", "quantity": 70,  "status": "in_transit", "priority": "normal", "notes": None},
    {"id": 33, "row_number": 5,  "delivery_day": "Sunday",    "client": "METS MANUFAC ELECTRO.DE SOUSSE",    "driver": "Sami Hamdi",         "vehicle": "TU-624-EE", "start_location": "COFICAB Mégrine", "end_location": "SIDI ABDELHMID",  "distance_km": 163.0, "etd": "05:30", "eta": "09:15", "quantity": 250, "status": "in_transit", "priority": "high",   "notes": "Early departure"},
    {"id": 34, "row_number": 6,  "delivery_day": "Sunday",    "client": "ADC Sousse",                        "driver": "Riadh Bouzid",       "vehicle": "TU-731-FF", "start_location": "COFICAB Mégrine", "end_location": "SOUSE",           "distance_km": 161.0, "etd": "05:00", "eta": "09:00", "quantity": 280, "status": "pending",    "priority": "high",   "notes": None},
    {"id": 35, "row_number": 7,  "delivery_day": "Sunday",    "client": "COFAT KAIROUAN",                    "driver": "Bilel Ayari",        "vehicle": "TU-840-GG", "start_location": "COFICAB Mégrine", "end_location": "KAIRAOUEN",       "distance_km": 170.0, "etd": "05:00", "eta": "09:15", "quantity": 310, "status": "pending",    "priority": "urgent", "notes": "Must arrive before 09:30"},
    {"id": 36, "row_number": 8,  "delivery_day": "Sunday",    "client": "I.C.eM",                            "driver": "Hatem Khelifi",      "vehicle": "TU-955-HH", "start_location": "COFICAB Mégrine", "end_location": "BNI KHALLED",     "distance_km": 57.4,  "etd": "09:00", "eta": "10:30", "quantity": 100, "status": "pending",    "priority": "normal", "notes": None},
]

@router.get("/transports")
async def get_transports(
    status: Optional[str] = Query(None),
    day: Optional[str] = Query(None),
    limit: int = Query(100),
    offset: int = Query(0),
    db: Optional[Session] = Depends(get_db_optional)
):
    """Retrieve all livraisons/transports - public endpoint"""
    try:
        # If database is available, fetch real data
        if db:
            query = db.query(Livraison)

            # Apply filters if provided
            if status:
                query = query.filter(Livraison.status == status)
            if day:
                query = query.filter(Livraison.delivery_day == day)

            # Get total count
            total = query.count()

            # Apply pagination
            livraisons = query.offset(offset).limit(limit).all()

            # Convert to response format
            transport_list = []
            for livraison in livraisons:
                transport_list.append({
                    "id": livraison.id,
                    "row_number": livraison.row_number,
                    "delivery_day": livraison.delivery_day,
                    "delivery_date": livraison.delivery_date.isoformat() if livraison.delivery_date else None,
                    "client": livraison.client,
                    "driver": livraison.driver,
                    "vehicle": livraison.vehicle,
                    "etd": livraison.etd,
                    "eta": livraison.eta,
                    "quantity": livraison.quantity,
                    "start_location": livraison.start_location,
                    "end_location": livraison.end_location,
                    "distance_km": livraison.distance_km,
                    "status": livraison.status,
                    "priority": livraison.priority,
                    "notes": livraison.notes,
                    "created_at": livraison.created_at.isoformat() if livraison.created_at else None
                })

            return {
                "transports": transport_list,
                "total": total
            }
        else:
            # Return mock data filtered by day if provided
            mock = MOCK_TRANSPORTS
            if status:
                mock = [t for t in mock if t.get("status") == status]
            if day:
                mock = [t for t in mock if t.get("delivery_day") == day]
            paginated = mock[offset: offset + limit]
            return {"transports": paginated, "total": len(mock)}

    except Exception as e:
        # Return mock data on error
        mock = MOCK_TRANSPORTS
        if day:
            mock = [t for t in mock if t.get("delivery_day") == day]
        return {
            "transports": mock[:limit],
            "total": len(mock),
            "error": f"Database error: {str(e)}"
        }

@router.get("/ingestion-history")
async def get_ingestion_history(
    limit: int = Query(50),
    db: Optional[Session] = Depends(get_db_optional)
):
    """Get ingestion processing history"""
    try:
        if db:
            ingestion_service = IngestionService(db)
            history = ingestion_service.get_ingestion_history(limit)
            return {"history": history}
        else:
            return {
                "history": [
                    {
                        "id": 1,
                        "file_name": "weekly_planning.xlsx",
                        "import_date": "2026-05-06T10:00:00",
                        "status": "success",
                        "inserted_rows": 25,
                        "total_rows": 25,
                        "error_message": None
                    }
                ]
            }
    except Exception as e:
        return {
            "history": [],
            "error": f"Failed to retrieve history: {str(e)}"
        }

@router.get("/stats")
async def get_data_stats(db: Optional[Session] = Depends(get_db_optional)):
    """Get data statistics"""
    try:
        if db:
            # Count livraisons by status
            status_counts = {}
            for status in ["pending", "in_transit", "completed"]:
                count = db.query(Livraison).filter(Livraison.status == status).count()
                status_counts[status] = count

            # Total livraisons
            total_livraisons = db.query(Livraison).count()

            # Recent imports
            recent_imports = db.query(IngestionLog).filter(
                IngestionLog.status == "success"
            ).order_by(IngestionLog.import_date.desc()).limit(5).all()

            return {
                "total_livraisons": total_livraisons,
                "status_breakdown": status_counts,
                "recent_imports": len(recent_imports),
                "last_import": recent_imports[0].import_date.isoformat() if recent_imports else None
            }
        else:
            return {
                "total_livraisons": 2,
                "status_breakdown": {"pending": 0, "in_transit": 1, "completed": 1},
                "recent_imports": 1,
                "last_import": "2026-05-06T10:00:00"
            }
    except Exception as e:
        return {
            "total_livraisons": 0,
            "status_breakdown": {"pending": 0, "in_transit": 0, "completed": 0},
            "recent_imports": 0,
            "error": f"Failed to get stats: {str(e)}"
        }