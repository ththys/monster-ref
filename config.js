// 몬스터 레퍼런스 아카이브 설정
// 자세한 순서는 README.md 를 보세요.

window.REF_CONFIG = {
  // 1) 데이터 저장 (Firebase)
  //    Firebase 콘솔 > 프로젝트 설정 > 내 앱(웹)의 firebaseConfig 값을 그대로 붙여 넣으세요.
  //    비워 두면 "이 브라우저에만 저장" 모드로 동작합니다.
  firebase: {
    apiKey: "여기에 붙여 넣기",
    authDomain: "",
    projectId: "",
    storageBucket: "",
    messagingSenderId: "",
    appId: ""
  },

  // 2) 이미지·영상 저장 (Cloudinary, 무료)
  //    새로 올리는 파일은 목록의 "마지막" 계정으로 올라갑니다.
  //    첫 계정이 가득 차면 아래에 한 줄 더 추가하세요. 이전 파일은 원래 계정에서 계속 보입니다.
  //    비워 두면 작은 이미지만 데이터 안에 함께 저장합니다.
  cloudinary: [
    { cloudName: "여기에 붙여 넣기", uploadPreset: "monster_ref" }
    // , { cloudName: "두번째계정", uploadPreset: "monster_ref" }
  ],

  // 3) 편집할 수 있는 구글 계정 (firestore.rules 의 이메일과 똑같이)
  editors: ["본인 구글 이메일"]
};
