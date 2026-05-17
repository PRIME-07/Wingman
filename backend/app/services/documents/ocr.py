import base64
import fitz  # PyMuPDF
from typing import List, Optional
from openai import AsyncOpenAI
from backend.app.core.config import settings
from backend.app.core.logging import logger
from backend.app.services.credentials.manager import credential_manager

class OCRService:
    """
    High-fidelity Vision OCR service that utilizes GPT-4o-mini to extract 
    structured Markdown from document images.
    """
    
    def __init__(self):
        self.model = settings.OCR_MODEL

    async def _get_client(self) -> Optional[AsyncOpenAI]:
        """Resolves OpenAI API key with Tiered Lookup (Env -> Mongo) and returns Async client."""
        api_key = await credential_manager.get_secret("openai_api_key", provider="engine")
        if not api_key:
            return None
        return AsyncOpenAI(api_key=api_key)

    async def process_pdf(self, file_bytes: bytes) -> str:
        """
        Converts PDF pages to images and performs Vision-based OCR.
        
        :param file_bytes: Raw PDF bytes.
        :returns: Combined Markdown text from all pages.
        """
        client = await self._get_client()
        if not client:
            logger.warning("[OCR-Service] No OpenAI API Key found in Environment or Database. Skipping Deep Scan.")
            return ""

        try:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            full_text_blocks = []

            for page_num in range(len(doc)):
                logger.info(f"[OCR-Service] Processing page {page_num + 1}/{len(doc)}")
                page = doc.load_page(page_num)
                
                # Convert page to high-res image (300 DPI for OCR clarity)
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                img_bytes = pix.tobytes("png")
                
                # Perform the Vision call
                markdown_content = await self._get_markdown_from_image(client, img_bytes, page_num + 1)
                if markdown_content:
                    full_text_blocks.append(f"--- PAGE {page_num + 1} ---\n{markdown_content}")

            doc.close()
            return "\n\n".join(full_text_blocks)

        except Exception as e:
            logger.error(f"[OCR-Service] Critical failure in Vision pipeline: {e}", exc_info=True)
            return ""

    async def _get_markdown_from_image(self, client: AsyncOpenAI, img_bytes: bytes, page_num: int) -> Optional[str]:
        """Sends a single image to GPT-4o-mini for transcription."""
        base64_image = base64.b64encode(img_bytes).decode('utf-8')
        
        try:
            response = await client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a professional document digitizer. Your task is to extract all text, "
                            "tables, and structural elements from the provided image. "
                            "Return the content in clean, valid Markdown. Preserve table relationships "
                            "exactly as they appear. Do not include any conversational text or preamble."
                        )
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text", 
                                "text": f"Please transcribe page {page_num} of this document."
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=2048,
                temperature=0.0
            )
            
            content = response.choices[0].message.content
            return content.strip() if content else None

        except Exception as e:
            logger.error(f"[OCR-Service] OpenAI request failed for page {page_num}: {e}")
            return None

# Singleton instance
ocr_service = OCRService()
