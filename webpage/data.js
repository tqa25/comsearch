/* ============================================
 * SECTION: Pipeline Data
 * PURPOSE: Dữ liệu mô tả 5 module của hệ thống
 * MODIFY: Sửa nội dung text, thêm bớt tag, thay đổi ví dụ ở đây
 * ============================================ */

const PIPELINE_DATA = [
  {
    id: 1,
    theme: "blue",
    title: {
      en: "Module 1",
      name: "Gemini Grounding"
    },
    inputs: [
      { type: "text", text: "Company English Name" }
    ],
    outputs: [
      { type: "tag", text: "VN Name" },
      { type: "tag", text: "EN Name" },
      { type: "tag", text: "Tax Code" },
      { type: "tag", text: "Address" },
      { type: "tag", text: "URLs (placeholder)" }
    ],
    whyText: {
      vi: "Gemini Grounding kết nối trực tiếp với Google Search, xác định chính xác VN/EN Name và Tax Code — nền tảng bắt buộc để toàn bộ pipeline tìm đúng công ty.",
      ko: "AI가 구글과 직접 연결되어 베트남/영어 이름과 사업자등록번호를 정확히 파악합니다. 파이프라인 전체가 정확한 회사를 찾기 위한 필수 기반입니다."
    },
    connectionLabel: {
      vi: "Company info: VN/EN Name · Tax Code · URLs",
      ko: "회사 정보: 베트남/영어 이름 · 사업자등록번호 · 웹사이트 링크"
    },
    details: {
      example: {
        vi: "Input: 'Samsung Vietnam' → AI tìm kiếm và trả về Tên tiếng Việt: 'Công ty TNHH Điện tử Samsung Vina', Mã số thuế: '0301323264'.",
        ko: "입력: 'Samsung Vietnam' → AI가 검색하여 베트남어 이름 'Công ty TNHH Điện tử Samsung Vina'와 사업자등록번호 '0301323264'를 찾아냅니다."
      },
      glossary: [
        { 
          term: "Gemini Grounding", 
          vi: "Tính năng cho phép AI tự động tra cứu thông tin trên Google Search theo thời gian thực để lấy dữ liệu mới nhất.", 
          ko: "AI가 실시간으로 구글 검색을 통해 최신 데이터를 찾아보는 기능입니다."
        },
        { 
          term: "Tax Code", 
          vi: "Mã số thuế - mã định danh duy nhất của doanh nghiệp, giúp tránh nhầm lẫn giữa các công ty trùng tên.", 
          ko: "사업자등록번호 - 이름이 같은 다른 회사와 혼동을 피하기 위한 회사의 고유 식별 번호입니다."
        }
      ]
    }
  },
  {
    id: 2,
    theme: "green",
    title: {
      en: "Module 2",
      name: "Scraper Search – Vòng lặp"
    },
    isLoop: true, // Chỉ định đây là module có flowchart vòng lặp
    inputs: [
      { type: "text", text: "VN/EN Name, Tax Code, URLs" } // Ẩn trong UI gốc, nhưng cần cho logic
    ],
    outputs: [
      { type: "tag", text: "<10 URLs, score >35" },
      { type: "tag", text: "Best available nếu <10" },
      { type: "tag", text: "Không trùng lặp" }
    ],
    whyText: {
      vi: "Vòng lặp if-else đảm bảo chất lượng output: chỉ chấp nhận URLs có điểm >35 và mở rộng tìm kiếm (2.2 → 2.3) nếu chưa đủ 10. Dedup trước khi score ở mỗi vòng đảm bảo 10 URLs cuối đa dạng nguồn, không trùng, không lãng phí lượt crawl ở Module 3.",
      ko: "조건부 반복을 통해 결과 품질을 보장합니다. 점수가 35점 이상인 링크만 인정하며 10개가 안 되면 검색을 확장합니다. 중복을 제거하여 다음 단계에서 불필요한 작업 비용을 줄입니다."
    },
    connectionLabel: {
      vi: "10 URLs đã filter, dedup và score >35",
      ko: "필터링, 중복 제거, 점수 평가(35점 이상) 완료된 링크 10개"
    },
    details: {
      example: {
        vi: "Vòng 1 tìm được 100 links, chấm điểm xong có 6 links > 35 điểm. Do < 10, hệ thống tự động qua Vòng 2 tìm thêm 100 links khác, loại bỏ trùng với Vòng 1, chấm điểm được thêm 5 links. Tổng = 11 links > 35 điểm → Dừng sớm (Early Stop) lấy top 10.",
        ko: "1라운드에서 100개 링크 중 35점 이상이 6개 발견됨. 10개 미만이므로 자동으로 2라운드를 진행하여 100개를 더 찾고 1라운드와 중복을 제거. 5개를 추가로 찾아 총 11개가 되어 조기 중단(Early Stop) 후 상위 10개를 선택함."
      },
      glossary: [
        { 
          term: "Dedup (Deduplication)", 
          vi: "Loại bỏ các kết quả trùng lặp để không xử lý cùng một trang web nhiều lần.", 
          ko: "같은 웹사이트를 여러 번 처리하지 않도록 중복된 결과를 제거하는 과정입니다."
        },
        { 
          term: "Scoring", 
          vi: "Chấm điểm từng trang web dựa trên khả năng chứa thông tin liên hệ (số điện thoại, email). Điểm cao = khả năng chứa thông tin tốt.", 
          ko: "연락처(전화번호, 이메일 등)가 있을 가능성을 기준으로 각 웹페이지에 점수를 매깁니다."
        }
      ]
    }
  },
  {
    id: 3,
    theme: "red",
    title: {
      en: "Module 3",
      name: "Firecrawl"
    },
    inputs: [
      { type: "text", text: "10 URLs" }
    ],
    outputs: [
      { type: "tag", text: "Raw content ×10" },
      { type: "tag", text: "Markdown text" }
    ],
    whyText: {
      vi: "Firecrawl chuyển HTML thành markdown sạch, loại noise (ads, nav, footer). Giảm token khi đưa vào Gemini ở bước sau, tăng chất lượng extract.",
      ko: "웹페이지(HTML)를 깔끔한 텍스트(마크다운)로 변환하고 광고, 메뉴, 하단 정보 등 불필요한 부분을 제거합니다. 다음 단계에서 AI가 분석할 데이터 양을 줄여 정확도를 높입니다."
    },
    connectionLabel: {
      vi: "Raw crawled content từ 10 trang",
      ko: "10개 웹페이지에서 수집한 원본 텍스트 데이터"
    },
    details: {
      example: {
        vi: "Trang web 'dienmayxanh.com' nặng 5MB chứa đầy ảnh và quảng cáo → Firecrawl quét và biến thành 1 đoạn văn bản thuần (markdown) chỉ chứa text và danh sách chi nhánh, kích thước giảm xuống còn 15KB.",
        ko: "'dienmayxanh.com' 웹페이지는 사진과 광고가 많아 5MB 크기임 → 이 도구가 스캔하여 텍스트와 지점 목록만 있는 15KB 크기의 깔끔한 문서로 변환함."
      },
      glossary: [
        { 
          term: "Firecrawl", 
          vi: "Công cụ chuyên dụng để đọc (crawl) các trang web hiện đại và trích xuất nội dung văn bản chính.", 
          ko: "최신 웹페이지를 읽고 주요 텍스트 내용만 추출하는 전문 도구입니다."
        },
        { 
          term: "Markdown", 
          vi: "Định dạng văn bản đơn giản (chỉ có chữ, tiêu đề, danh sách) rất dễ cho AI đọc hiểu so với mã code HTML phức tạp.", 
          ko: "복잡한 웹페이지 코드(HTML)에 비해 AI가 읽고 이해하기 매우 쉬운 간단한 텍스트 형식입니다."
        }
      ]
    }
  },
  {
    id: 4,
    theme: "blue",
    title: {
      en: "Module 4",
      name: "Gemini Extract"
    },
    inputs: [
      { type: "text", text: "Raw content ×10" },
      { type: "text", text: "Extraction schema" }
    ],
    outputs: [
      { type: "tag", text: "Structured company data" },
      { type: "tag", text: "VN/EN Name ✓" },
      { type: "tag", text: "Tax Code ✓" },
      { type: "tag", text: "Address ✓" }
    ],
    whyText: {
      vi: "Cross-verify thông tin từ nhiều nguồn thực tế. Gemini với schema chuẩn hóa output thành JSON nhất quán, tăng độ tin cậy so với Module 1.",
      ko: "여러 실제 출처의 정보를 교차 검증합니다. AI가 정해진 양식에 맞춰 일관성 있는 데이터로 출력하여 모듈 1보다 신뢰도를 높입니다."
    },
    connectionLabel: {
      vi: "Structured data đã xác minh",
      ko: "검증된 구조화된 데이터"
    },
    details: {
      example: {
        vi: "AI đọc nội dung từ 10 trang web khác nhau. 3 trang có chứa số điện thoại '028-3123-4567'. AI xác nhận đây là số chính xác nhất và trả về định dạng chuẩn { \"phone\": \"028-3123-4567\", \"address\": \"...\" }.",
        ko: "AI가 10개의 다른 웹페이지 내용을 읽음. 3개 페이지에 '028-3123-4567' 전화번호가 있음. AI가 이를 가장 정확한 번호로 확인하고 표준 형식 { \"phone\": \"028-3123-4567\", \"address\": \"...\" }으로 출력함."
      },
      glossary: [
        { 
          term: "Extraction schema", 
          vi: "Khuôn mẫu yêu cầu AI phải trả về dữ liệu đúng hình thức định sẵn (ví dụ: bắt buộc phải có cột Tên, cột SĐT).", 
          ko: "AI가 정해진 형식에 맞게 데이터를 반환하도록 요구하는 틀입니다 (예: 이름 칸, 전화번호 칸 필수 포함)."
        },
        { 
          term: "Structured data", 
          vi: "Dữ liệu đã được sắp xếp gọn gàng thành các trường rõ ràng (JSON) thay vì một đoạn văn bản lộn xộn.", 
          ko: "뒤죽박죽인 텍스트가 아니라 명확한 항목별로 깔끔하게 정리된 데이터입니다."
        }
      ]
    }
  },
  {
    id: 5,
    theme: "purple",
    title: {
      en: "Module 5",
      name: "Format Output"
    },
    inputs: [
      { type: "text", text: "Structured company data" },
      { type: "text", text: "Markdown template" }
    ],
    outputs: [
      { type: "tag", text: "Formatted Markdown" },
      { type: "tag", text: "UI-ready display" }
    ],
    whyText: {
      vi: "Tách riêng format để thay đổi UI mà không cần chạy lại pipeline. Template đảm bảo output nhất quán, dễ nâng cấp giao diện về sau.",
      ko: "파이프라인 전체를 다시 실행하지 않고도 디자인(UI)을 바꿀 수 있도록 서식 지정 단계를 분리합니다. 템플릿을 사용하여 결과물을 일관성 있게 만들고 향후 업그레이드를 쉽게 합니다."
    },
    connectionLabel: null, // Module cuối không có arrow trỏ đi
    details: {
      example: {
        vi: "Lấy dữ liệu JSON ở Module 4, điền vào một file template có sẵn để tạo ra một bản báo cáo PDF/Markdown đẹp mắt gửi cho khách hàng, có logo và bảng biểu rõ ràng.",
        ko: "모듈 4의 데이터를 가져와 미리 준비된 템플릿에 채워 넣음으로써 로고와 표가 깔끔하게 들어간 고객용 보고서 문서를 생성합니다."
      },
      glossary: [
        { 
          term: "UI-ready", 
          vi: "Trạng thái dữ liệu đã sẵn sàng để hiển thị trực tiếp lên giao diện người dùng (ví dụ: màn hình ứng dụng web).", 
          ko: "사용자 화면(예: 웹 앱 화면)에 바로 표시할 준비가 된 데이터 상태입니다."
        }
      ]
    }
  }
];

// Data cho vòng lặp của Module 2
const MODULE_2_FLOWCHART = {
  rounds: [
    { id: "2.1", label: "Search 2.1", subLabel: "100 URLs" },
    { id: "2.2", label: "Search 2.2", subLabel: "100 URLs" },
    { id: "2.3", label: "Search 2.3", subLabel: "100 URLs" }
  ],
  steps: [
    { id: "dedup", labelVi: "Dedup", labelKo: "중복제거" },
    { id: "scoring", labelVi: "Scoring\\nchấm điểm", labelKo: "점수매기기" },
    { id: "decision", labelVi: "≥10 URLs\\n>35 điểm?", labelKo: "35점 이상\\n10개 이상?" }
  ]
};
