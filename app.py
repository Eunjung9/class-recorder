import streamlit as st
from firebase_admin import credentials, firestore, initialize_app, storage, auth
import firebase_admin
import pandas as pd
import tempfile
import os

# Firebase 초기화
if not firebase_admin._apps:
    cred = credentials.Certificate("firebase_key.json")
    initialize_app(cred, {
        'storageBucket': 'class-recorder99.firebasestorage.app'
    })

db = firestore.client()
bucket = storage.bucket()

# 인증 상태 저장용 세션
if "user" not in st.session_state:
    st.session_state.user = None

# 로그인 기능 구현
def login():
    st.subheader("로그인")
    email = st.text_input("이메일")
    password = st.text_input("비밀번호", type="password")
    if st.button("로그인"):
        try:
            user = auth.get_user_by_email(email)
            st.session_state.user = user
            st.success("로그인 성공")
        except:
            st.error("로그인 실패. 사용자 정보를 확인하세요.")

# 로그아웃
if st.session_state.user:
    if st.button("로그아웃"):
        st.session_state.user = None
        st.experimental_rerun()

# 교과 추가
def add_subject():
    st.subheader("교과 추가")
    name = st.text_input("교과명")
    year = st.number_input("학년도", step=1)
    semester = st.selectbox("학기", [1, 2])
    file = st.file_uploader("수업계획서 PDF 업로드 (10MB 이하)", type=['pdf'])

    if st.button("저장"):
        if file and file.type == "application/pdf" and file.size <= 10 * 1024 * 1024:
            blob = bucket.blob(f"syllabus/{file.name}")
            blob.upload_from_file(file, content_type='application/pdf')
            url = blob.public_url

            db.collection("subjects").add({
                "name": name,
                "year": year,
                "semester": semester,
                "pdf_url": url
            })
            st.success("교과가 추가되었습니다.")
        else:
            st.error("PDF 형식이며 10MB 이하의 파일만 업로드 가능합니다.")

# 교과 목록 조회
def view_subjects():
    st.subheader("교과 목록")
    subjects = db.collection("subjects").stream()
    data = []
    for subj in subjects:
        s = subj.to_dict()
        s['id'] = subj.id
        data.append(s)
    if data:
        df = pd.DataFrame(data)
        st.dataframe(df)
    else:
        st.info("등록된 교과가 없습니다.")

# 수업 등록
def add_class():
    st.subheader("수업 등록")
    year = st.number_input("학년도", step=1)
    semester = st.selectbox("학기", [1, 2])
    subjects = db.collection("subjects").stream()
    subject_options = {f"{subj.to_dict()['name']} ({subj.id})": subj.id for subj in subjects}
    subject_id = st.selectbox("교과 선택", list(subject_options.keys()))
    class_name = st.text_input("수업 학반 이름")
    weekday = st.selectbox("요일", ['월', '화', '수', '목', '금'])
    period = st.number_input("교시", step=1)

    if st.button("수업 저장"):
        db.collection("classes").add({
            "year": year,
            "semester": semester,
            "subject_id": subject_options[subject_id],
            "class_name": class_name,
            "weekday": weekday,
            "period": period
        })
        st.success("수업이 저장되었습니다.")

# 학생 등록/CSV 업로드
def add_students():
    st.subheader("학생 등록")
    classes = db.collection("classes").stream()
    class_options = {f"{cls.to_dict()['class_name']} ({cls.id})": cls.id for cls in classes}
    selected_class = st.selectbox("수업반 선택", list(class_options.keys()))

    option = st.radio("등록 방식", ["직접 입력", "CSV 업로드"])

    if option == "직접 입력":
        sid = st.text_input("학번")
        name = st.text_input("성명")
        if st.button("학생 추가"):
            db.collection("students").add({
                "student_id": sid,
                "name": name,
                "class_id": class_options[selected_class]
            })
            st.success("학생이 추가되었습니다.")

    else:
        file = st.file_uploader("CSV 업로드", type=['csv'])
        if file:
            df = pd.read_csv(file)
            for _, row in df.iterrows():
                db.collection("students").add({
                    "student_id": row['학번'],
                    "name": row['성명'],
                    "class_id": class_options[selected_class]
                })
            st.success("CSV에서 학생들이 등록되었습니다.")

# 진도 및 특기사항 기록
def record_progress():
    st.subheader("진도 및 특기사항 기록")
    classes = db.collection("classes").stream()
    class_options = {f"{cls.to_dict()['class_name']} ({cls.id})": cls.id for cls in classes}
    selected_class = st.selectbox("수업반 선택", list(class_options.keys()))
    date = st.date_input("날짜")
    period = st.number_input("교시", step=1)
    content = st.text_area("진도 내용")
    note = st.text_area("특기사항")

    if st.button("기록 저장"):
        db.collection("progress").add({
            "class_id": class_options[selected_class],
            "date": str(date),
            "period": period,
            "content": content,
            "note": note
        })
        st.success("기록이 저장되었습니다.")

# 출결 기록
def record_attendance():
    st.subheader("출결 및 특기사항 기록")
    classes = db.collection("classes").stream()
    class_options = {f"{cls.to_dict()['class_name']} ({cls.id})": cls.id for cls in classes}
    selected_class = st.selectbox("수업반 선택", list(class_options.keys()))

    students = db.collection("students").where("class_id", "==", class_options[selected_class]).stream()
    student_options = {f"{stu.to_dict()['name']} ({stu.to_dict()['student_id']})": stu.id for stu in students}
    selected_student = st.selectbox("학생 선택", list(student_options.keys()))

    date = st.date_input("날짜")
    status = st.selectbox("출결 상태", ["출석", "지각", "결석", "미확인"])
    note = st.text_area("특기사항")

    if st.button("출결 저장"):
        db.collection("attendance").add({
            "class_id": class_options[selected_class],
            "student_id": student_options[selected_student],
            "date": str(date),
            "status": status,
            "note": note
        })
        st.success("출결 정보가 저장되었습니다.")

# 전체 진도 조회
def view_progress():
    st.subheader("진도 전체 조회")
    date = st.date_input("조회 날짜")
    progresses = db.collection("progress").where("date", "==", str(date)).stream()
    data = [doc.to_dict() for doc in progresses]
    st.dataframe(pd.DataFrame(data))

# 전체 출결 조회
def view_attendance():
    st.subheader("출결 전체 조회")
    date = st.date_input("조회 날짜")
    records = db.collection("attendance").where("date", "==", str(date)).stream()
    data = [doc.to_dict() for doc in records]
    st.dataframe(pd.DataFrame(data))

# 메뉴 구성
menu = ["로그인", "교과 추가", "교과 목록", "수업 등록", "학생 등록", "진도 기록", "출결 기록", "진도 조회", "출결 조회"]
choice = st.sidebar.selectbox("메뉴", menu)

if choice == "로그인":
    login()
elif st.session_state.user:
    if choice == "교과 추가":
        add_subject()
    elif choice == "교과 목록":
        view_subjects()
    elif choice == "수업 등록":
        add_class()
    elif choice == "학생 등록":
        add_students()
    elif choice == "진도 기록":
        record_progress()
    elif choice == "출결 기록":
        record_attendance()
    elif choice == "진도 조회":
        view_progress()
    elif choice == "출결 조회":
        view_attendance()
else:
    st.warning("먼저 로그인해주세요.")
