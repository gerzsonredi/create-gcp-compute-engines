json_schema = {
    "name": "clothing_item_condition",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "condition_rating": {"type": "number", "enum": list(range(1,11))},
            "condition_description": {"type": "string"}
        },
        "required": ["condition_rating", "condition_description"],
        "additionalProperties": False
    }
}

prompt_message = (
    "Rate the garment on the images on a scale of 1-10. 1 is the worst quality and 10 being excellent quality, brand new. "
    "Look out for the following defects: dirty, pilling, colorfading, stretching, holes, etc. Don't take into account if the clothing item is wrinkled. Wrinkling doesn't affect the condition of the item. "
    "Write a detailed condition report in the condition description field. Write down the defects you detected, their size and position. "
    "Write down any damage, deterioration or alterations that you see. "
    "If there is a tag that does not necessarily mean that it's brand new, don't base your opinion off of that. Don't mention the tag in the description either. "
    "If you see a hooded item, the holes for the hood strings do not count as defects. "
    "If you see ripped jeans, that's most likely part of the design, it doesn't count as defect. "
    "Only describe the errors, damage, deterioration, alterations or defects in the description (if there are any). Keep it short 1 or 2 sentences."
    "The description should be in a textstyle that could be published onto an ecommerce platform for viewers to see. "
    "If you don't see any errors, then just leave the description empty, don't write anything and leave condition_description field an empty string."

)

json_schema2 = {
    "name": "clothing_item_attributes",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "identification": {
                "type": "object",
                "properties": {
                    "internal_id": {"type": "string"},
                    "brand": {"type": "string"},
                    "certifications": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": [
                                "EN ISO 20471 high visibility",
                                "EN ISO 14058 protection against cool",
                                "EN ISO 13688 protective clothing",
                                "EN ISO 11612 protection againt heat and flame",
                                "EN ISO 16111 protection during welding",
                                ""
                            ]
                        }
                    }
                },
                "required": ["internal_id", "brand", "certifications"],
                "additionalProperties": False
            },
            "garment_classification": {
                "type": "object", 
                "properties": {
                    "main_category": {
                        "type": "string",
                        "enum": ["PPE", "Workwear", "Business Clothing & Uniforms", "Hygienic Clothing", "Basics"]
                    },
                    "subcategory": {"type": "string"},
                    "size_tag": {"type": "string"},
                    "size_measured": {"type": "string"},
                    "description": {"type": "string"},
                },
                "required": ["main_category", "subcategory", "size_tag", "size_measured", "description"],
                "additionalProperties": False
            },
            "color_visibility": {
                "type": "object",
                "properties": {
                    "primary_color": {"type": "string"},
                    "secondary_colors": {"type": "string"}
                },
                "required": ["primary_color", "secondary_colors"],
                "additionalProperties": False
            },
            "materials_construction": {
                "type": "object",
                "properties": {
                    "fabric_composition": {"type": "string"},
                    "closure_type": {"type": "string"},
                    "cuff_style": {"type": "string"},
                    "hem_waist_style": {"type": "string"},
                    "collar_type": {"type": "string"},
                    "ventilation_features": {"type": "string"},
                    "stretch_panels": {"type": "boolean"},
                    "wash_resistance": {"type": "string"}
                },
                "required": ["fabric_composition", "closure_type", "cuff_style", "hem_waist_style", "collar_type", "ventilation_features", "stretch_panels", "wash_resistance"],
                "additionalProperties": False
            },
            "functional_features": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": [
                        "Tool pockets",
                        "Chest pockets", 
                        "Knee pad pockets",
                        "ID badge holder",
                        "Hammer loop",
                        "Reinforced elbows",
                        "Reinforced knees",
                        "Stretch fabric panels",
                        "Concealed fastenings",
                        "Ventilation zones",
                        "Hygienic design (no external pockets)",
                        "Detachable sleeves",
                        "Detachable hood",
                        "Multinorm compliance"
                    ]
                }
            },
            "condition_reusability": {
                "type": "object",
                "properties": {
                    "condition_grade": {"type": "number"},
                    "condition_note": {"type": "string"},
                    "visible_defects": {"type": "boolean"},
                    "defect_types": {"type": "string"},
                    "defect_locations": {"type": "string"},
                    "repair_needed": {"type": "boolean"},
                    "ppe_reuse_viable": {"type": "boolean"}
                },
                "required": ["condition_grade", "condition_note", "visible_defects", "defect_types", "defect_locations", "repair_needed", "ppe_reuse_viable"],
                "additionalProperties": False
            }
        },
        "required": ["identification", "garment_classification", "color_visibility", "materials_construction", "functional_features", "condition_reusability"],
        "additionalProperties": False
    }
}

prompt_message2 = (
    "Please analyze these images of work clothing and provide detailed information according to the following categories:\n"
    "\n"
    "1. Basic identification including brand and any visible certifications. Determine the certifications based on the symbols you see in the labels. For example if you see a fire simbol on the label it means that the garment has \"EN ISO 11612 protection againt heat and flame\" etc. Look for the symbols. Choose the empty string option if you don't see any certifications. \n"
    "2. Garment classification - specify if it's PPE, workwear, business uniform, etc. and the specific type of garment. In the description give a brief description of the garment, don't mention the condition here. Include the number of pockets the garment has, use definitive language. \n" 
    "3. Color details - primary and secondary colors\n"
    "4. Materials and construction - fabric composition, closure types, cuff style, collar type, etc.\n"
    "5. Functional features - identify any special pockets, reinforcements, or functional elements\n"
    "6. Condition assessment - grade the condition from 1-10, note any visible defects or needed repairs. Be short but detailed in your answers here. Give me answers that aren't human like responses, but rather categorical. I'm looking for answers that could be choosen on a resale platform for example. \n"
    "\n"
    "Please be as specific and detailed as possible in your analysis. If certain details are not visible in the images, indicate that by leaving your answers blank for that particular thing in the following way: \"\""
)

json_schema3 = {
    "name": "clothing_item_attributes",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "gen": {
                "type": "string",
                "enum": ["Femei/Ladies", "Bărbați/Men"]
            },
            "mărime": {
                "type": "string", 
                "enum": ["XXS", "XS", "S", "M", "L", "XL", "XXL", "XXXL"]
            },
            "culoare": {
                "type": "string",
                "enum": ["Negru/Black", "Alb/White", "Roșu/Red", "Albastru/Blue", "Gri/Gray", "Bej/Beige", "Verde/Green", "Galben/Yellow",
                        "Roz/Pink", "Mov/Purple", "Portocaliu/Orange", "Maro/Brown", "Turcoaz/Turquoise", "Multicolor/Multicolor", "Argintiu/Silver", "Auriu/Gold"]
            },
            "brand": {
                "type": "string",
                "enum": ["Zara", "H&M", "Nike", "Adidas", "Bershka", "Pull&Bear", "Levi's", "Puma",
                        "Stradivarius", "Tally Weijl", "Mango", "Tommy Hilfiger", "Guess", "Reebok",
                        "Superdry", "Weekday", "Monki", "NA-KD", "Only", "Vero Moda", "Reserved",
                        "Victoria's Secret", "Under Armour", "Urban Classics", "Vintage", "No Brand"]
            },
            "stare": {
                "type": "string",
                "enum": ["Nou/New", "Second Hand/Second Hand", "Vintage/Vintage"]
            },
            "condiție": {
                "type": "string", 
                "enum": ["10/10", "9/10", "8/10"]
            },
            "tags": {
                "type": "string"
            }
        },
        "required": ["gen", "mărime", "culoare", "brand", "stare", "condiție", "tags"],
        "additionalProperties": False
    }
}

prompt_message3 = (
    "Please analyze these clothing item images and provide the following details:\n"
    "\n"
    "1. Gender (gen) - Specify if the item is for women (Femei) or men (Bărbați)\n"
    "2. Size (mărime) - Identify the size from XXS to XXXL\n"
    "3. Color (culoare) - Determine the main color of the item\n"
    "4. Brand - Identify the brand name from the label or design\n"
    "5. Item Status (stare) - Classify if the item is New (Nou), Second Hand, or Vintage\n"
    "6. Condition (condiție) - Rate the item's condition as 10/10 (perfect), 9/10 (excellent), or 8/10 (very good)\n"
    "7. Tags - Write 10 tags that could be applied for the clothing item. These are searchable tags, that could be applied to shopify. Tags could be the following: Fresh, Only 1 of Each, New Arrivals, Sale, Set VierVier, Animal Print, Stylist's Hotlist, Seasonal Sale or anything else that you think is applicable. \n"
    "\n"
    "Please be precise and only use the exact values specified for each category. If you cannot determine any attribute with certainty, do not make assumptions."
)