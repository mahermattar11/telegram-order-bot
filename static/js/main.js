// انتظار تحميل الصفحة بالكامل
document.addEventListener('DOMContentLoaded', function() {
    
    // 1. إدارة الشريط الجانبي للجوال
    const sidebar = document.getElementById('sidebar');
    const content = document.getElementById('content');
    const sidebarToggle = document.getElementById('sidebarToggle');
    
    // إنشاء زر التبديل إذا لم يكن موجوداً (للجوال)
    if (!sidebarToggle && window.innerWidth < 768) {
        const toggleBtn = document.createElement('button');
        toggleBtn.id = 'sidebarToggle';
        toggleBtn.className = 'btn btn-primary d-md-none mobile-toggle';
        toggleBtn.innerHTML = '<i class="bi bi-list"></i>';
        document.querySelector('main').prepend(toggleBtn);
        
        toggleBtn.addEventListener('click', toggleSidebar);
    } else if (sidebarToggle) {
        sidebarToggle.addEventListener('click', toggleSidebar);
    }
    
    // دالة تبديل الشريط الجانبي
    function toggleSidebar() {
        sidebar.classList.toggle('active');
        content.classList.toggle('sidebar-collapsed');
        
        // تغيير الأيقونة
        const icon = sidebarToggle.querySelector('i');
        if (sidebar.classList.contains('active')) {
            icon.className = 'bi bi-x-lg';
        } else {
            icon.className = 'bi bi-list';
        }
    }

    // 2. تحديث حالة الطلب عبر API
    window.updateOrderStatus = function(orderId, newStatus, element) {
        const statusText = {
            'new': 'جديد',
            'processing': 'قيد التنفيذ', 
            'completed': 'مكتمل',
            'cancelled': 'ملغي'
        };
        
        if (confirm(`هل تريد تغيير حالة الطلب إلى "${statusText[newStatus]}"؟`)) {
            // إظهار تحميل
            if (element) {
                const originalText = element.innerHTML;
                element.innerHTML = '<i class="bi bi-hourglass-split"></i>';
                element.disabled = true;
            }
            
            fetch(`/api/orders/${orderId}/status`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ status: newStatus })
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(data => {
                if (data.success) {
                    showNotification('success', 'تم تحديث حالة الطلب بنجاح');
                    
                    // تحديث واجهة المستخدم دون إعادة تحميل
                    const statusBadge = document.querySelector(`tr[data-order-id="${orderId}"] .order-status`);
                    if (statusBadge) {
                        updateStatusBadge(statusBadge, newStatus);
                    }
                    
                    // تحديث الإحصائيات إذا كانت موجودة
                    updateStats(data.stats);
                    
                } else {
                    showNotification('error', 'حدث خطأ: ' + (data.error || 'غير معروف'));
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showNotification('error', 'فشل الاتصال بالسيرفر');
            })
            .finally(() => {
                // إعادة الزر لحالته الأصلية
                if (element) {
                    element.innerHTML = originalText;
                    element.disabled = false;
                }
            });
        }
    };

    // 3. حذف الطلب
    window.deleteOrder = function(orderId, element) {
        if (confirm('هل أنت متأكد من حذف هذا الطلب نهائياً؟')) {
            if (element) {
                const originalText = element.innerHTML;
                element.innerHTML = '<i class="bi bi-trash"></i> حذف...';
                element.disabled = true;
            }
            
            fetch(`/api/orders/${orderId}`, {
                method: 'DELETE',
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showNotification('success', 'تم حذف الطلب بنجاح');
                    
                    // إزالة الصف من الجدول
                    const row = document.querySelector(`tr[data-order-id="${orderId}"]`);
                    if (row) {
                        row.style.opacity = '0';
                        setTimeout(() => row.remove(), 300);
                    }
                    
                    // تحديث الإحصائيات
                    updateStats(data.stats);
                    
                } else {
                    showNotification('error', 'حدث خطأ أثناء الحذف');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showNotification('error', 'فشل الاتصال بالسيرفر');
            })
            .finally(() => {
                if (element) {
                    element.innerHTML = originalText;
                    element.disabled = false;
                }
            });
        }
    };

    // 4. تأثيرات بصرية وتحسينات UX
    const cards = document.querySelectorAll('.card-custom');
    cards.forEach(card => {
        card.addEventListener('mouseenter', () => {
            card.style.transform = 'translateY(-5px)';
            card.style.transition = 'transform 0.3s ease, box-shadow 0.3s ease';
            card.style.boxShadow = '0 10px 25px rgba(0,0,0,0.1)';
        });
        
        card.addEventListener('mouseleave', () => {
            card.style.transform = 'translateY(0)';
            card.style.boxShadow = '0 4px 12px rgba(0,0,0,0.05)';
        });
    });

    // 5. تنبيهات الطلبات الجديدة
    function checkNewOrders() {
        fetch('/api/orders/new/count')
            .then(response => response.json())
            .then(data => {
                const newOrdersBadge = document.querySelector('.new-orders-badge');
                if (newOrdersBadge && data.count > 0) {
                    newOrdersBadge.textContent = data.count;
                    newOrdersBadge.classList.remove('d-none');
                    
                    // تنبيه إذا كانت هناك طلبات جديدة
                    if (data.count > parseInt(newOrdersBadge.dataset.lastCount || 0)) {
                        showNotification('info', `لديك ${data.count} طلبات جديدة`);
                    }
                    newOrdersBadge.dataset.lastCount = data.count;
                }
            });
    }
    
    // التحقق من الطلبات الجديدة كل 30 ثانية
    setInterval(checkNewOrders, 30000);
    
    // 6. وظائف مساعدة
    function showNotification(type, message) {
        // إنشاء عنصر التنبيه
        const alert = document.createElement('div');
        alert.className = `alert alert-${type === 'success' ? 'success' : type === 'error' ? 'danger' : 'info'} alert-dismissible fade show position-fixed`;
        alert.style.cssText = 'top: 20px; left: 50%; transform: translateX(-50%); z-index: 9999; min-width: 300px;';
        alert.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        document.body.appendChild(alert);
        
        // إزالة التنبيه بعد 5 ثوانٍ
        setTimeout(() => {
            alert.classList.remove('show');
            setTimeout(() => alert.remove(), 300);
        }, 5000);
    }
    
    function updateStatusBadge(badgeElement, newStatus) {
        const statusClasses = {
            'new': 'bg-warning',
            'processing': 'bg-info',
            'completed': 'bg-success',
            'cancelled': 'bg-danger'
        };
        
        const statusText = {
            'new': 'جديد',
            'processing': 'قيد التنفيذ',
            'completed': 'مكتمل',
            'cancelled': 'ملغي'
        };
        
        // إزالة جميع كلاسات الحالة
        Object.values(statusClasses).forEach(cls => {
            badgeElement.classList.remove(cls);
        });
        
        // إضافة الكلاس والنص الجديد
        badgeElement.classList.add(statusClasses[newStatus]);
        badgeElement.textContent = statusText[newStatus];
    }
    
    function updateStats(newStats) {
        // تحديث أرقام الإحصائيات بسلاسة
        const statsElements = {
            'total_orders': document.querySelector('.total-orders'),
            'new_orders': document.querySelector('.new-orders'),
            'completed_orders': document.querySelector('.completed-orders'),
            'today_orders': document.querySelector('.today-orders')
        };
        
        Object.keys(statsElements).forEach(key => {
            const element = statsElements[key];
            if (element && newStats[key] !== undefined) {
                animateCounter(element, newStats[key]);
            }
        });
    }
    
    function animateCounter(element, targetValue) {
        const currentValue = parseInt(element.textContent) || 0;
        const duration = 500; // ملي ثانية
        const step = (targetValue - currentValue) / (duration / 16);
        let current = currentValue;
        
        const timer = setInterval(() => {
            current += step;
            if ((step > 0 && current >= targetValue) || (step < 0 && current <= targetValue)) {
                element.textContent = targetValue;
                clearInterval(timer);
            } else {
                element.textContent = Math.round(current);
            }
        }, 16);
    }

    // 7. تهيئة الأزرار التفاعلية
    initializeActionButtons();
    
    function initializeActionButtons() {
        // أزرار تغيير الحالة
        document.querySelectorAll('.status-btn').forEach(btn => {
            btn.addEventListener('click', function() {
                const orderId = this.dataset.orderId;
                const newStatus = this.dataset.status;
                updateOrderStatus(orderId, newStatus, this);
            });
        });
        
        // أزرار الحذف
        document.querySelectorAll('.delete-btn').forEach(btn => {
            btn.addEventListener('click', function() {
                const orderId = this.dataset.orderId;
                deleteOrder(orderId, this);
            });
        });
        
        // أزرار التفاصيل
        document.querySelectorAll('.details-btn').forEach(btn => {
            btn.addEventListener('click', function() {
                const orderId = this.dataset.orderId;
                showOrderDetails(orderId);
            });
        });
    }
    
    // 8. عرض تفاصيل الطلب
    window.showOrderDetails = function(orderId) {
        fetch(`/api/orders/${orderId}`)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // إنشاء modal لعرض التفاصيل
                    createDetailsModal(data.order);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showNotification('error', 'فشل في جلب تفاصيل الطلب');
            });
    };
    
    function createDetailsModal(order) {
        const modalHtml = `
            <div class="modal fade" id="orderDetailsModal" tabindex="-1">
                <div class="modal-dialog modal-lg">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">تفاصيل الطلب #${order.id}</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <div class="row">
                                <div class="col-md-6">
                                    <h6>معلومات العميل</h6>
                                    <p><strong>الاسم:</strong> ${order.name}</p>
                                    <p><strong>الهاتف:</strong> ${order.phone || 'غير محدد'}</p>
                                    <p><strong>البريد:</strong> ${order.email || 'غير محدد'}</p>
                                </div>
                                <div class="col-md-6">
                                    <h6>معلومات الطلب</h6>
                                    <p><strong>المنتج:</strong> ${order.product}</p>
                                    <p><strong>الكمية:</strong> ${order.quantity}</p>
                                    <p><strong>السعر:</strong> ${order.price || 'غير محدد'}</p>
                                    <p><strong>التاريخ:</strong> ${order.created_at}</p>
                                </div>
                            </div>
                            ${order.notes ? `<div class="mt-3"><h6>ملاحظات:</h6><p>${order.notes}</p></div>` : ''}
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">إغلاق</button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        // إضافة الـmodal إلى body وعرضه
        const modalContainer = document.createElement('div');
        modalContainer.innerHTML = modalHtml;
        document.body.appendChild(modalContainer);
        
        const modal = new bootstrap.Modal(document.getElementById('orderDetailsModal'));
        modal.show();
        
        // تنظيف الـmodal بعد إغلاقه
        document.getElementById('orderDetailsModal').addEventListener('hidden.bs.modal', function() {
            modalContainer.remove();
        });
    }

    // 9. تحسين تجربة الجوال
    function handleMobileView() {
        if (window.innerWidth < 768) {
            // إخفاء الشريط الجانبي تلقائياً في الجوال
            if (!sidebar.classList.contains('active')) {
                sidebar.classList.remove('active');
                content.classList.add('sidebar-collapsed');
            }
        } else {
            // إظهار الشريط الجانبي في الشاشات الكبيرة
            sidebar.classList.add('active');
            content.classList.remove('sidebar-collapsed');
        }
    }
    
    // التحقق عند تغيير حجم النافذة
    window.addEventListener('resize', handleMobileView);
    handleMobileView(); // التحقق عند التحميل
});