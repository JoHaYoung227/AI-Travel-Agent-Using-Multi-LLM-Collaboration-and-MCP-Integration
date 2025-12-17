// 날짜 최소값 설정 (오늘 이후만 선택 가능)
function setMinDate() {
    const today = new Date();
    const tomorrow = new Date(today);
    tomorrow.setDate(tomorrow.getDate() + 1);
    
    const dateString = tomorrow.toISOString().split('T')[0];
    
    const departureDate = document.getElementById('departure_date');
    const returnDate = document.getElementById('return_date');
    
    if (departureDate) {
        departureDate.min = dateString;
        departureDate.value = dateString;
    }
    
    if (returnDate) {
        const dayAfterTomorrow = new Date(tomorrow);
        dayAfterTomorrow.setDate(dayAfterTomorrow.getDate() + 2);
        returnDate.min = dateString;
        returnDate.value = dayAfterTomorrow.toISOString().split('T')[0];
    }
}

// 출발일 변경 시 도착일 최소값 업데이트
document.getElementById('departure_date')?.addEventListener('change', function(e) {
    const departureDate = new Date(e.target.value);
    const returnDateInput = document.getElementById('return_date');
    
    if (returnDateInput) {
        const nextDay = new Date(departureDate);
        nextDay.setDate(nextDay.getDate() + 1);
        returnDateInput.min = nextDay.toISOString().split('T')[0];
        
        // 도착일이 출발일보다 이전이면 자동 조정
        const returnDate = new Date(returnDateInput.value);
        if (returnDate <= departureDate) {
            const suggestedReturn = new Date(departureDate);
            suggestedReturn.setDate(suggestedReturn.getDate() + 2);
            returnDateInput.value = suggestedReturn.toISOString().split('T')[0];
        }
    }
});

// 예산 실시간 포맷팅
document.getElementById('budget')?.addEventListener('input', function(e) {
    const value = parseInt(e.target.value) || 0;
    const display = document.querySelector('.budget-display');
    if (display) {
        display.textContent = `₩ ${value.toLocaleString('ko-KR')}`;
    }
});

// 출발지/도착지 교환
function swapLocations() {
    const origin = document.getElementById('origin');
    const destination = document.getElementById('destination');
    
    if (origin && destination) {
        const temp = origin.value;
        origin.value = destination.value;
        destination.value = temp;
        
        // 애니메이션 효과
        origin.style.transform = 'scale(0.95)';
        destination.style.transform = 'scale(0.95)';
        
        setTimeout(() => {
            origin.style.transform = 'scale(1)';
            destination.style.transform = 'scale(1)';
        }, 200);
    }
}

// 빠른 선택 버튼 (날짜 기반)
function setDestination(dest, departureDate, returnDate, budget) {
    document.getElementById('destination').value = dest;
    document.getElementById('departure_date').value = departureDate;
    document.getElementById('return_date').value = returnDate;
    document.getElementById('budget').value = budget;

    // 🔥 스타일 필드 업데이트 추가
    const styleSelect = document.getElementById('travel_style');
    if (styleSelect) {
        styleSelect.value = style;
    }
    
    // 예산 디스플레이 업데이트
    const display = document.querySelector('.budget-display');
    if (display) {
        display.textContent = `₩ ${budget.toLocaleString('ko-KR')}`;
    }
    
    // 시각적 피드백
    const chip = event.target;
    chip.style.transform = 'scale(1.05)';
    setTimeout(() => {
        chip.style.transform = 'scale(1)';
    }, 200);
}

// 폼 제출 시 로딩 표시
document.getElementById('travelForm')?.addEventListener('submit', function(e) {
    const submitBtn = this.querySelector('.submit-btn');
    if (submitBtn) {
        submitBtn.innerHTML = '<span>🔄 계획 생성 중...</span>';
        submitBtn.disabled = true;
    }
});

// 페이지 로드 시 초기화
window.addEventListener('load', function() {
    // 날짜 최소값 설정
    setMinDate();
    
    const searchCard = document.querySelector('.search-card');
    if (searchCard) {
        searchCard.style.opacity = '0';
        searchCard.style.transform = 'translateY(20px)';
        
        setTimeout(() => {
            searchCard.style.transition = 'all 0.6s ease';
            searchCard.style.opacity = '1';
            searchCard.style.transform = 'translateY(0)';
        }, 100);
    }
    
    // 결과 페이지 애니메이션
    const dayCards = document.querySelectorAll('.day-card');
    dayCards.forEach((card, index) => {
        card.style.opacity = '0';
        card.style.transform = 'translateX(-20px)';
        
        setTimeout(() => {
            card.style.transition = 'all 0.5s ease';
            card.style.opacity = '1';
            card.style.transform = 'translateX(0)';
        }, 100 + (index * 100));
    });
});

// 스크롤 애니메이션
const observerOptions = {
    threshold: 0.1,
    rootMargin: '0px 0px -50px 0px'
};

const observer = new IntersectionObserver(function(entries) {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.style.opacity = '1';
            entry.target.style.transform = 'translateY(0)';
        }
    });
}, observerOptions);

// 관찰할 요소들
document.querySelectorAll('.feature, .summary-card, .sidebar-card').forEach(el => {
    el.style.opacity = '0';
    el.style.transform = 'translateY(20px)';
    el.style.transition = 'all 0.6s ease';
    observer.observe(el);
});

// 인쇄 최적화
window.addEventListener('beforeprint', function() {
    document.querySelectorAll('.action-buttons, .back-btn').forEach(el => {
        el.style.display = 'none';
    });
});

window.addEventListener('afterprint', function() {
    document.querySelectorAll('.action-buttons, .back-btn').forEach(el => {
        el.style.display = '';
    });
});

// script.js에 추가
function goToPlanner() {
    document.getElementById('landing-page').classList.remove('active');
    document.getElementById('planner-page').classList.add('active');
}

// script.js에 추가
document.getElementById('travelForm').addEventListener('submit', function(e) {
    e.preventDefault();
    
    // 로딩 페이지 표시
    document.getElementById('planner-page').classList.remove('active');
    document.getElementById('loading-page').classList.add('active');
    
    // 폼 제출
    this.submit();
});
