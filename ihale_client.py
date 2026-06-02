#!/usr/bin/env python3
"""
EKAP v2 API client for Turkish government tender/procurement data.

Stripped version: only the methods used by main.py.
"""

import httpx
import ssl
import os
import uuid
import base64
import time
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding as crypto_padding
from typing import Dict, Any, Optional, List, Literal
from datetime import datetime


class EKAPClient:
    """Client for EKAP v2 API"""

    def __init__(self):
        self.base_url = "https://ekapv2.kik.gov.tr"
        self.tender_endpoint = "/b_ihalearama/api/Ihale/GetListByParameters"
        self.tender_details_endpoint = "/b_ihalearama/api/IhaleDetay/GetByIhaleIdIhaleDetay"
        self.document_url_endpoint = "/b_ihalearama/api/EkapDokumanYonlendirme/GetDokumanUrl"

        # AES key for request signing (from EKAP frontend environment config)
        self._r8fact_key = b'Qm2LtXR0aByP69vZNKef4wMJ'

        # Common headers for all requests
        self.headers = {
            'Accept': 'application/json',
            'Accept-Language': 'tr',
            'Connection': 'keep-alive',
            'Content-Type': 'application/json',
            'Origin': 'https://ekapv2.kik.gov.tr',
            'Referer': 'https://ekapv2.kik.gov.tr/ekap/search',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
            'api-version': 'v1',
            'sec-ch-ua': '"Not)A;Brand";v="8", "Chromium";v="138", "Google Chrome";v="138"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"macOS"'
        }

    def _create_ssl_context(self) -> ssl.SSLContext:
        """Create SSL context that supports older protocols"""
        ssl_context = ssl.create_default_context()
        ssl_context.set_ciphers('DEFAULT@SECLEVEL=1')
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        return ssl_context

    def _aes_cbc_encrypt(self, plaintext: str, key: bytes, iv: bytes) -> bytes:
        """Encrypt plaintext with AES-CBC and PKCS7 padding."""
        padder = crypto_padding.PKCS7(128).padder()
        padded = padder.update(plaintext.encode()) + padder.finalize()
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
        enc = cipher.encryptor()
        return enc.update(padded) + enc.finalize()

    def _generate_security_headers(self) -> Dict[str, str]:
        """Generate AES-signed security headers required by EKAP v2 API."""
        guid = str(uuid.uuid4())
        iv = os.urandom(16)
        ts_ms = str(int(time.time() * 1000))

        r8id = base64.b64encode(self._aes_cbc_encrypt(guid, self._r8fact_key, iv)).decode()
        ts_enc = base64.b64encode(self._aes_cbc_encrypt(ts_ms, self._r8fact_key, iv)).decode()
        siv = base64.b64encode(iv).decode()

        return {
            'X-Custom-Request-Guid': guid,
            'X-Custom-Request-Siv': siv,
            'X-Custom-Request-Ts': ts_enc,
            'X-Custom-Request-R8id': r8id,
        }

    async def _make_request(self, endpoint: str, params: dict) -> dict:
        """Make an API request to EKAP v2"""
        ssl_context = self._create_ssl_context()
        request_headers = {**self.headers, **self._generate_security_headers()}

        async with httpx.AsyncClient(
            timeout=30.0,
            verify=ssl_context,
            http2=False,
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
        ) as client:
            response = await client.post(
                f"{self.base_url}{endpoint}",
                json=params,
                headers=request_headers
            )
            response.raise_for_status()
            return response.json()

    def _format_date_for_api(self, date_str: Optional[str]) -> Optional[str]:
        """Validate and return date in YYYY-MM-DD format expected by API"""
        if not date_str:
            return None
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
            return date_str
        except ValueError:
            return None

    async def search_tenders(
        self,
        search_text: str = "",
        ikn_year: Optional[int] = None,
        ikn_number: Optional[int] = None,
        tender_types: List[int] = None,
        tender_date_start: Optional[str] = None,
        tender_date_end: Optional[str] = None,
        announcement_date_start: Optional[str] = None,
        announcement_date_end: Optional[str] = None,
        search_type: Literal["GirdigimGibi", "TumKelimeler"] = "GirdigimGibi",
        order_by: Literal["ihaleTarihi", "ihaleAdi", "idareAdi"] = "ihaleTarihi",
        sort_order: Literal["asc", "desc"] = "desc",
        # Boolean filters
        e_ihale: Optional[bool] = None,
        e_eksiltme_yapilacak_mi: Optional[bool] = None,
        ortak_alim_mi: Optional[bool] = None,
        kismi_teklif_mi: Optional[bool] = None,
        fiyat_disi_unsur_varmi: Optional[bool] = None,
        ekonomik_mali_yeterlilik_belgeleri_isteniyor_mu: Optional[bool] = None,
        mesleki_teknik_yeterlilik_belgeleri_isteniyor_mu: Optional[bool] = None,
        is_deneyimi_gosteren_belgeler_isteniyor_mu: Optional[bool] = None,
        yerli_istekliye_fiyat_avantaji_uygulanıyor_mu: Optional[bool] = None,
        yabanci_isteklilere_izin_veriliyor_mu: Optional[bool] = None,
        alternatif_teklif_verilebilir_mi: Optional[bool] = None,
        konsorsiyum_katilabilir_mi: Optional[bool] = None,
        alt_yuklenici_calistirilabilir_mi: Optional[bool] = None,
        fiyat_farki_verilecek_mi: Optional[bool] = None,
        avans_verilecek_mi: Optional[bool] = None,
        cerceve_anlasmasi_mi: Optional[bool] = None,
        personel_calistirilmasina_dayali_mi: Optional[bool] = None,
        # List filters
        provinces: List[int] = None,
        tender_statuses: List[int] = None,
        tender_methods: List[int] = None,
        tender_sub_methods: List[int] = None,
        okas_codes: List[str] = None,
        okas_names: List[str] = None,
        authority_ids: List[int] = None,
        proposal_types: List[int] = None,
        announcement_types: List[int] = None,
        # Search scope parameters
        search_in_ikn: bool = True,
        search_in_title: bool = True,
        search_in_announcement: bool = True,
        search_in_tech_spec: bool = True,
        search_in_admin_spec: bool = True,
        search_in_similar_work: bool = True,
        search_in_location: bool = True,
        search_in_nature_quantity: bool = True,
        search_in_tender_info: bool = True,
        search_in_contract_draft: bool = True,
        search_in_bid_form: bool = True,
        skip: int = 0,
        limit: int = 10
    ) -> Dict[str, Any]:
        """Search for Turkish government tenders"""

        api_params = {
            "searchText": search_text,
            "filterType": None,
            "ikNdeAra": search_in_ikn,
            "ihaleAdindaAra": search_in_title,
            "ihaleIlanindaAra": search_in_announcement,
            "teknikSartnamedeAra": search_in_tech_spec,
            "idariSartnamedeAra": search_in_admin_spec,
            "benzerIsMaddesindeAra": search_in_similar_work,
            "isinYapilacagiYerMaddesindeAra": search_in_location,
            "nitelikTurMiktarMaddesindeAra": search_in_nature_quantity,
            "ihaleBilgilerindeAra": search_in_tender_info,
            "sozlesmeTasarisindaAra": search_in_contract_draft,
            "teklifCetvelindeAra": search_in_bid_form,
            "searchType": search_type,
            "iknYili": ikn_year,
            "iknSayi": ikn_number,
            "ihaleTarihSaatBaslangic": self._format_date_for_api(tender_date_start),
            "ihaleTarihSaatBitis": self._format_date_for_api(tender_date_end),
            "ilanTarihSaatBaslangic": self._format_date_for_api(announcement_date_start),
            "ilanTarihSaatBitis": self._format_date_for_api(announcement_date_end),
            "yasaKapsami4734List": [],
            "ihaleTuruIdList": tender_types or [],
            "ihaleUsulIdList": tender_methods or [],
            "ihaleUsulAltIdList": tender_sub_methods or [],
            "ihaleIlIdList": provinces or [],
            "ihaleDurumIdList": tender_statuses or [],
            "idareKodList": authority_ids or [],
            "ihaleIlanTuruIdList": announcement_types or [],
            "teklifTuruIdList": proposal_types or [],
            "asiriDusukTeklifIdList": [],
            "istisnaMaddeIdList": [],
            "okasBransKodList": okas_codes or [],
            "okasBransAdiList": okas_names or [],
            "titubbKodList": [],
            "gmdnKodList": [],
            "eIhale": e_ihale,
            "eEksiltmeYapilacakMi": e_eksiltme_yapilacak_mi,
            "ortakAlimMi": ortak_alim_mi,
            "kismiTeklifMi": kismi_teklif_mi,
            "fiyatDisiUnsurVarmi": fiyat_disi_unsur_varmi,
            "ekonomikVeMaliYeterlilikBelgeleriIsteniyorMu": ekonomik_mali_yeterlilik_belgeleri_isteniyor_mu,
            "meslekiTeknikYeterlilikBelgeleriIsteniyorMu": mesleki_teknik_yeterlilik_belgeleri_isteniyor_mu,
            "isDeneyimiGosterenBelgelerIsteniyorMu": is_deneyimi_gosteren_belgeler_isteniyor_mu,
            "yerliIstekliyeFiyatAvantajiUgulaniyorMu": yerli_istekliye_fiyat_avantaji_uygulanıyor_mu,
            "yabanciIsteklilereIzinVeriliyorMu": yabanci_isteklilere_izin_veriliyor_mu,
            "alternatifTeklifVerilebilirMi": alternatif_teklif_verilebilir_mi,
            "konsorsiyumKatilabilirMi": konsorsiyum_katilabilir_mi,
            "altYukleniciCalistirilabilirMi": alt_yuklenici_calistirilabilir_mi,
            "fiyatFarkiVerilecekMi": fiyat_farki_verilecek_mi,
            "avansVerilecekMi": avans_verilecek_mi,
            "cerceveAnlasmaMi": cerceve_anlasmasi_mi,
            "personelCalistirilmasinaDayaliMi": personel_calistirilmasina_dayali_mi,
            "orderBy": order_by,
            "siralamaTipi": sort_order,
            "paginationSkip": skip,
            "paginationTake": limit
        }

        try:
            response_data = await self._make_request(self.tender_endpoint, api_params)

            tenders = response_data.get("list", [])
            total_count = response_data.get("totalCount", 0)

            formatted_tenders = []
            for tender in tenders:
                tender_id = tender.get("id")

                document_url = None
                if tender_id and tender.get("dokumanSayisi", 0) > 0:
                    try:
                        doc_result = await self.get_tender_document_url(tender_id)
                        if doc_result.get("success"):
                            document_url = doc_result.get("document_url")
                    except Exception:
                        pass

                formatted_tender = {
                    "id": tender_id,
                    "name": tender.get("ihaleAdi"),
                    "ikn": tender.get("ikn"),
                    "type": {
                        "code": tender.get("ihaleTip"),
                        "description": tender.get("ihaleTipAciklama")
                    },
                    "method": tender.get("ihaleUsulAciklama"),
                    "status": {
                        "code": tender.get("ihaleDurum"),
                        "description": tender.get("ihaleDurumAciklama")
                    },
                    "authority": tender.get("idareAdi"),
                    "province": tender.get("ihaleIlAdi"),
                    "tender_datetime": tender.get("ihaleTarihSaat"),
                    "document_count": tender.get("dokumanSayisi", 0),
                    "has_announcement": tender.get("ilanVarMi", False),
                    "document_url": document_url
                }
                formatted_tenders.append(formatted_tender)

            return {
                "tenders": formatted_tenders,
                "total_count": total_count,
                "returned_count": len(formatted_tenders)
            }

        except httpx.HTTPStatusError as e:
            return {
                "error": f"API request failed with status {e.response.status_code}",
                "message": str(e)
            }
        except Exception as e:
            return {
                "error": "Request failed",
                "message": str(e)
            }

    async def get_tender_details_raw(
        self,
        tender_id: str
    ) -> Dict[str, Any]:
        """Get raw tender details document directly from the API (no formatting)."""

        details_params = {"ihaleId": tender_id}

        try:
            return await self._make_request(self.tender_details_endpoint, details_params)
        except httpx.HTTPStatusError as e:
            return {
                "error": f"API request failed with status {e.response.status_code}",
                "message": str(e)
            }
        except Exception as e:
            return {
                "error": "Request failed - tender details (raw)",
                "message": str(e)
            }

    async def get_tender_document_url(
        self,
        tender_id: str,
        islem_id: str = "1"
    ) -> Dict[str, Any]:
        """Get document URL for a specific tender"""

        document_params = {
            "islemId": islem_id,
            "ihaleId": tender_id
        }

        try:
            response_data = await self._make_request(self.document_url_endpoint, document_params)
            document_url = response_data.get("url")

            if document_url:
                return {
                    "document_url": document_url,
                    "tender_id": tender_id,
                    "islem_id": islem_id,
                    "success": True
                }
            return {
                "error": "No document URL found",
                "tender_id": tender_id,
                "success": False
            }

        except httpx.HTTPStatusError as e:
            return {
                "error": f"API request failed with status {e.response.status_code}",
                "message": str(e),
                "success": False
            }
        except Exception as e:
            return {
                "error": "Request failed - tender document URL",
                "message": str(e),
                "success": False
            }
