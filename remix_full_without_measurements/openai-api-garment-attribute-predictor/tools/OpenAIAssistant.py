from openai import AsyncOpenAI
from typing import Any, Dict, List
import json, asyncio

class OpenAIAssistant:
    def __init__(self, api_key: str):
        self.__client = AsyncOpenAI(api_key=api_key)

    async def extract_work_clothing_info(
            self,
            image_urls:List[str],
            json_schema:Dict[str, Any],
            prompt_message:str,
            retries=3, 
            delay=2, 
            model="gpt-4o"
        ):

        system_prompt = (
            "You are an expert in work clothing product analysis. "
            "You will receive images of the same garment. "
            "Use all images to determine it's attributes. "
        )

        # 3 images (or fewer if not available)
        user_content = [{"type": "text", "text": prompt_message}]
        for url in image_urls:
            user_content.append({"type": "image_url", "image_url": {"url": url}})

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_content}
        ]
        
        for attempt in range(1, retries + 1):
            try:
                res = await self.__client.chat.completions.create(
                    model=model,
                    temperature=0,
                    response_format={
                        "type": "json_schema",
                        "json_schema": json_schema
                    },
                    messages=messages,
                )
                return json.loads(res.choices[0].message.content)

            except Exception as e:
                print(f"Attempt {attempt} failed for item {image_urls[0]}: {e}")
                await asyncio.sleep(delay)
        return {k: "" for k in json_schema["schema"]["properties"].keys()}
    
    async def extract_data_romanian(
            self,
            image_urls:List[str],
            json_schema:Dict[str, Any],
            prompt_message:str,
            retries=3, 
            delay=2, 
            model="gpt-4.1"    
        ):

        system_prompt = (
            "You are an expert in clothing product analysis. "
            "You will receive images of the same garment. "
            "Use all images to determine it's attributes. "
            "You need to determine the attributes in romanian language. "
        )

        # 3 images (or fewer if not available)
        user_content = [{"type": "text", "text": prompt_message}]
        for url in image_urls:
            user_content.append({"type": "image_url", "image_url": {"url": url}})

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_content}
        ]
        
        for attempt in range(1, retries + 1):
            try:
                res = await self.__client.chat.completions.create(
                    model=model,
                    temperature=0,
                    response_format={
                        "type": "json_schema",
                        "json_schema": json_schema
                    },
                    messages=messages,
                )
                return json.loads(res.choices[0].message.content)

            except Exception as e:
                print(f"Attempt {attempt} failed for item {image_urls[0]}: {e}")
                await asyncio.sleep(delay)
        return {k: "" for k in json_schema["schema"]["properties"].keys()}
    

    async def extract_data(
            self, 
            image_urls:List[str],
            json_schema:Dict[str, Any],
            prompt_message:str,
            retries=3, 
            delay=2, 
            model="gpt-4.1"
        ):
        
        system_prompt = (
            "You are an expert in fashion product analysis. "
            "You will receive 3 images of the same garment. "
            "Use all images to determine it's attributes.\n"
        )

        # 3 images (or fewer if not available)
        user_content = [{"type": "text", "text": prompt_message}]
        for url in image_urls:
            user_content.append({"type": "image_url", "image_url": {"url": url}})

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_content}
        ]

        for attempt in range(1, retries + 1):
            try:
                res = await self.__client.chat.completions.create(
                    model=model,
                    temperature=0,
                    response_format={
                        "type": "json_schema",
                        "json_schema": json_schema
                    },
                    messages=messages,
                )
                return json.loads(res.choices[0].message.content)

            except Exception as e:
                print(f"Attempt {attempt} failed for item {image_urls[0]}: {e}")
                await asyncio.sleep(delay)
        return {k: "" for k in json_schema["schema"]["properties"].keys()}
    
