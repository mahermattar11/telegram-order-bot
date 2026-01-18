// orders.js - وظائف إضافية لصفحة الطلبات

// تصفية الطلبات حسب البحث
function filterOrders() {
    const searchTerm = document.getElementById('searchInput').value.toLowerCase();
    const rows = document.querySelectorAll('#ordersTable tbody tr');
    
    rows.forEach(row => {
        const text = row.textContent.toLowerCase();
        row.style.display = text.includes(searchTerm) ? '' : 'none';
    });
}

// تصدير الطلبات المحددة
function exportSelectedOrders() {
    const selectedOrders = [];
    document.querySelectorAll('.order-checkbox:checked').forEach(cb => {
        selectedOrders.push(cb.dataset.orderId);
    });
    
    if (selectedOrders.length === 0) {
        Swal.fire({
            icon: 'warning',
            title: 'لا توجد طلبات محددة',
            text: 'يرجى تحديد طلبات للتصدير'
        });
        return;
    }
    
    // هنا يمكن إضافة كود التصدير
    console.log('طلبات محددة للتصدير:', selectedOrders);
}

// تحديث عدة طلبات دفعة واحدة
function bulkUpdateStatus(newStatus) {
    const selectedOrders = [];
    document.querySelectorAll('.order-checkbox:checked').forEach(cb => {
        selectedOrders.push(cb.dataset.orderId);
    });
    
    if (selectedOrders.length === 0) {
        Swal.fire({
            icon: 'warning',
            title: 'لا توجد طلبات محددة',
            text: 'يرجى تحديد طلبات للتحديث'
        });
        return;
    }
    
    Swal.fire({
        title: `تحديث ${selectedOrders.length} طلبات`,
        text: `هل تريد تغيير حالة الطلبات المحددة إلى "${newStatus}"؟`,
        icon: 'question',
        showCancelButton: true,
        confirmButtonText: 'نعم، قم بالتحديث',
        cancelButtonText: 'إلغاء'
    }).then((result) => {
        if (result.isConfirmed) {
            // تحديث جميع الطلبات المحددة
            selectedOrders.forEach(orderId => {
                updateOrderStatus(orderId, newStatus);
            });
        }
    });
}

// إضافة أدوات التحديد السريع
function addQuickSelectTools() {
    const toolsHtml = `
        <div class="d-flex gap-2 mb-3">
            <button class="btn btn-sm btn-outline-primary" onclick="selectAllOrders()">
                <i class="bi bi-check-all"></i> تحديد الكل
            </button>
            <button class="btn btn-sm btn-outline-secondary" onclick="deselectAllOrders()">
                <i class="bi bi-x-circle"></i> إلغاء التحديد
            </button>
            <button class="btn btn-sm btn-outline-success" onclick="bulkUpdateStatus('completed')">
                <i class="bi bi-check-circle"></i> تعيين كمكتمل
            </button>
            <button class="btn btn-sm btn-outline-danger" onclick="bulkUpdateStatus('cancelled')">
                <i class="bi bi-x-circle"></i> تعيين كملغي
            </button>
        </div>
    `;
    
    const table = document.querySelector('#ordersTable');
    if (table) {
        table.insertAdjacentHTML('beforebegin', toolsHtml);
    }
}

// تحديد جميع الطلبات
function selectAllOrders() {
    document.querySelectorAll('.order-checkbox').forEach(cb => cb.checked = true);
}

// إلغاء تحديد جميع الطلبات
function deselectAllOrders() {
    document.querySelectorAll('.order-checkbox').forEach(cb => cb.checked = false);
}

// تهيئة الصفحة عند التحميل
document.addEventListener('DOMContentLoaded', function() {
    // إضافة أدوات التحديد السريع
    addQuickSelectTools();
    
    // إضافة حدث للبحث الفوري
    const searchInput = document.getElementById('searchInput');
    if (searchInput) {
        searchInput.addEventListener('input', filterOrders);
    }
    
    // إضافة تأثيرات للصفوف
    const rows = document.querySelectorAll('#ordersTable tbody tr');
    rows.forEach(row => {
        row.addEventListener('mouseenter', () => {
            row.style.backgroundColor = 'rgba(0, 123, 255, 0.05)';
        });
        row.addEventListener('mouseleave', () => {
            row.style.backgroundColor = '';
        });
    });
});

// دالة مساعدة للتحقق من الاتصال
function checkConnection() {
    return navigator.onLine;
}

// إضافة تحذير إذا كان الاتصال ضعيفاً
if (!checkConnection()) {
    Swal.fire({
        icon: 'warning',
        title: 'اتصال إنترنت ضعيف',
        text: 'بعض الميزات قد لا تعمل بشكل صحيح',
        timer: 3000
    });
}