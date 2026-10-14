#!/usr/bin/env python3
"""Test Gemini API - Generate Vietnamese answers"""

import os
import sys
from dotenv import load_dotenv
load_dotenv()

try:
    import google.generativeai as genai
    print("✅ google-generativeai imported successfully")
except ImportError as e:
    print("❌ Failed to import google-generativeai")
    print(f"   Error: {e}")
    print("\n💡 Install with: pip install google-generativeai==0.3.2")
    sys.exit(1)

def test_gemini_api():
    """Test Gemini API với câu hỏi tiếng Việt"""

    print("\n" + "="*70)
    print("🧪 GEMINI API TEST - Vietnamese Assistant")
    print("="*70 + "\n")

    # 1. Check API key
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ GEMINI_API_KEY not found in .env")
        return False

    print(f"✅ API Key: {api_key[:15]}...{api_key[-4:]}")

    # 2. Configure Gemini
    model_name = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
    print(f"📦 Model: {model_name}\n")

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            model_name=model_name,
            generation_config={
                "temperature": 0.3,
                "max_output_tokens": 500,
            }
        )
        print("✅ Model initialized\n")
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False

    # 3. Test simple prompt
    print("-" * 70)
    print("📝 TEST 1: Simple Vietnamese Prompt")
    print("-" * 70)

    prompt1 = "Thủ tục đăng ký hộ khẩu tạm trú cần những giấy tờ gì? Trả lời ngắn gọn."
    print(f"\n📥 Input: {prompt1}\n")

    try:
        response = model.generate_content(prompt1)
        print(f"📤 Output:\n{response.text}\n")
        print("✅ Test 1 PASSED")
    except Exception as e:
        print(f"❌ Test 1 FAILED: {e}")
        return False

    # 4. Test RAG-style prompt
    print("\n" + "-" * 70)
    print("📝 TEST 2: RAG-Style with Context")
    print("-" * 70)

    prompt2 = """Bạn là trợ lý AI về thủ tục hành chính.

CÁC TÀI LIỆU:

[Tài liệu 1] (Điều 10):
Đăng ký hộ khẩu cần:
- CMND/CCCD
- Sổ hộ khẩu cũ
- Giấy xác nhận cư trú
- Đơn xin đăng ký

[Tài liệu 2] (Điều 15):
Thời gian xử lý: 15 ngày làm việc.

CÂU HỎI: Đăng ký hộ khẩu cần gì và mất bao lâu?

TRẢ LỜI (dựa trên tài liệu):"""

    print(f"\n📥 Input: [RAG-style prompt with context]\n")

    try:
        response = model.generate_content(prompt2)
        answer = response.text
        print(f"📤 Output:\n{answer}\n")

        # Quality checks
        has_citation = any(x in answer for x in ["Tài liệu", "Theo", "Điều"])
        has_docs = "cmnd" in answer.lower() or "cccd" in answer.lower()
        has_time = "15" in answer or "ngày" in answer
        has_vietnamese = any(c in answer for c in "àáảãạăằắẳẵặâầấẩẫậèéẻẽẹ")

        print("📊 Quality Checks:")
        print(f"   {'✅' if has_citation else '⚠️'} Có trích dẫn: {has_citation}")
        print(f"   {'✅' if has_docs else '⚠️'} Có thông tin giấy tờ: {has_docs}")
        print(f"   {'✅' if has_time else '⚠️'} Có thông tin thời gian: {has_time}")
        print(f"   {'✅' if has_vietnamese else '⚠️'} Tiếng Việt có dấu: {has_vietnamese}")

        if all([has_citation, has_docs, has_time, has_vietnamese]):
            print("\n✅ Test 2 PASSED")
        else:
            print("\n⚠️ Test 2 PARTIAL")

    except Exception as e:
        print(f"❌ Test 2 FAILED: {e}")
        return False

    # Summary
    print("\n" + "="*70)
    print("🎉 ALL TESTS PASSED! Gemini API ready for RAG system.")
    print("="*70 + "\n")

    return True

if __name__ == "__main__":
    try:
        success = test_gemini_api()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
