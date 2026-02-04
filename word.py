import streamlit as st
from docxtpl import DocxTemplate
import io

# إعدادات الصفحة
st.set_page_config(page_title="محرر وثائق Word", layout="centered")

st.title("📄 تعبئة القوالب التلقائية (Mail Merge)")
st.write("قم برفع قالب Word يحتوي على `{{ variable_name }}` لتعبئته.")

# 1. رفع الملف التمبلت
uploaded_file = st.file_uploader("اختر قالب Word (.docx)", type=["docx"])

if uploaded_file:
    # تحميل القالب في الذاكرة
    doc = DocxTemplate(uploaded_file)
    
    st.subheader("📝 أدخل البيانات المطلوبة")
    
    # 2. نموذج إدخال البيانات (مثال)
    with st.form("my_form"):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("اسم العميل", placeholder="مثلاً: محمد علي")
            date = st.date_input("التاريخ")
        with col2:
            contract_id = st.text_input("رقم العقد", placeholder="مثلاً: 2024-001")
            price = st.number_input("المبلغ", value=0)
        
        submit = st.form_submit_button("توليد الملف المعدل")

    if submit:
        # 3. تجهيز البيانات (Context)
        # الأسماء هنا يجب أن تطابق ما هو موجود داخل الـ {{ }} في ملف Word
        context = {
            'client_name': name,
            'contract_id': contract_id,
            'date': str(date),
            'price': f"{price:,} ريال"
        }
        
        # 4. معالجة الملف
        doc.render(context)
        
        # حفظ الملف في "بفر" (الذاكرة) لكي لا نعدل على الملف الأصلي
        buffer = io.BytesIO()
        doc.save(buffer)
        buffer.seek(0)
        
        st.success("✅ تم تجهيز الملف بنجاح!")
        
        # 5. زر تحميل الملف المعدل
        st.download_button(
            label="📥 تحميل الملف المعدل",
            data=buffer,
            file_name=f"contract_{name}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )

else:
    st.info("يرجى رفع ملف .docx للبدء.")