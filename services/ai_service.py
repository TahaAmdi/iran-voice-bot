from openai import AsyncOpenAI
from settings import settings
import logging

logger = logging.getLogger(__name__)

class AIService:
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL
        )

    async def generate_email(self, topic: str, custom_details: str = None) -> str:
        """
        تولید متن ایمیل با ساختار تمیز، پاراگراف‌بندی شده و لیستی.
        """
        
        details_instruction = ""
        if custom_details:
            details_instruction = (
                f"\n\nIMPORTANT: The user has provided specific details: '{custom_details}'. "
                "Incorporate these facts naturally using a bullet point list if possible."
            )

        # تغییرات اصلی در اینجا (System Prompt) است:
        system_prompt = (
            "You are a human rights activist. Write a formal, urgent, and visually structured protest email. "
            "Strictly follow these rules:\n"
            "1. **Length:** Keep the total length between **150 to 250 words**. (Going over this will break the email link).\n"
            "2. **Structure:** Use short paragraphs (max 2-3 sentences).\n"
            "3. **Formatting:** You MUST use bullet points ('-') for key facts or demands to make it skimmable.\n"
            "4. **Tone:** Professional, diplomatic, yet firm and demanding.\n"
            "5. **No Placeholders:** Do not use [Date] or [Your Name]. Sign as 'A Concerned Citizen'."
        )

        user_message = f"Topic: {topic}{details_instruction}"

        try:
            response = await self.client.chat.completions.create(
                model=settings.AI_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.7,
                max_tokens=300,
                top_p=0.9,
            )
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"AI Generation Error: {e}")
            return (
                "I am writing to urgently protest against human rights violations in Iran.\n\n"
                "- The situation is critical.\n"
                "- Immediate diplomatic action is required.\n\n"
                "Please stand with the people of Iran."
            )