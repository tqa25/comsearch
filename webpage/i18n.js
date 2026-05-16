/* ============================================
 * SECTION: Internationalization Data
 * PURPOSE: Các text tĩnh trên giao diện cho 2 ngôn ngữ
 * ============================================ */

const I18N = {
  vi: {
    pageTitle: "Auto Search Company — Pipeline Diagram",
    badge: "System Architecture",
    subtitle: "Luồng xử lý dữ liệu 5 modules tự động tìm kiếm thông tin doanh nghiệp",
    btnRun: "Run",
    lblInput: "INPUT",
    lblOutput: "OUTPUT",
    btnField: "+ field",
    lblWhyDoThis: "TẠI SAO CẦN BƯỚC NÀY",
    
    // Tooltip
    tooltipHover: "Hover để xem tổng quan",
    tooltipClick: "Click để xem chi tiết",
    
    // Modal
    modalTabs: {
      process: "Quy trình",
      flowchart: "Sơ đồ chi tiết",
      example: "Ví dụ minh họa",
      glossary: "Thuật ngữ"
    },
    
    // Flowchart specific
    flowLoop: "vòng lặp (tối đa 3 lần)",
    flowYes: "YES",
    flowNo: "NO",
    flowBestAvailable: "best available",
    flowExit: "Exit loop",
    flowLegendSearch: "Search",
    flowLegendDedup: "Dedup",
    flowLegendScoring: "Scoring",
    flowLegendRetry: "Retry (NO)"
  },
  ko: {
    pageTitle: "자동 검색 시스템 — 파이프라인 다이어그램",
    badge: "시스템 아키텍처",
    subtitle: "기업 정보를 자동 검색하는 5단계 모듈 데이터 처리 흐름",
    btnRun: "실행",
    lblInput: "입력",
    lblOutput: "출력",
    btnField: "+ 필드 추가",
    lblWhyDoThis: "이 단계가 필요한 이유",
    
    // Tooltip
    tooltipHover: "개요를 보려면 마우스를 올리세요",
    tooltipClick: "자세히 보려면 클릭하세요",
    
    // Modal
    modalTabs: {
      process: "처리 과정",
      flowchart: "상세 흐름도",
      example: "예시",
      glossary: "용어 설명"
    },
    
    // Flowchart specific
    flowLoop: "반복 (최대 3회)",
    flowYes: "예",
    flowNo: "아니오",
    flowBestAvailable: "최선 결과",
    flowExit: "반복 종료",
    flowLegendSearch: "검색",
    flowLegendDedup: "중복제거",
    flowLegendScoring: "점수평가",
    flowLegendRetry: "재시도 (아니오)"
  }
};
