document.addEventListener('DOMContentLoaded', function() {
    // تأكيد الحذف
    const deleteButtons = document.querySelectorAll('.delete-confirm');
    deleteButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            if (!confirm('Êtes-vous sûr de vouloir supprimer cet élément ?')) {
                e.preventDefault();
            }
        });
    });

    // تحديث حقل التاريخ تلقائياً
    const dateInputs = document.querySelectorAll('input[type="date"]');
    dateInputs.forEach(input => {
        if (!input.value) {
            input.valueAsDate = new Date();
        }
    });

    // إضافة تأكيد للخروج من النموذج إذا كانت هناك تغييرات
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        let formChanged = false;
        form.addEventListener('change', () => formChanged = true);
        window.addEventListener('beforeunload', (e) => {
            if (formChanged) {
                e.preventDefault();
                e.returnValue = '';
            }
        });
    });

    // تحسين البحث في الجداول
    function filterTable() {
        const searchText = document.getElementById('tableFilter')?.value.toLowerCase() || '';
        const statusFilter = document.getElementById('statusFilter')?.value || '';
        const table = document.querySelector('.table tbody');
        const rows = table?.getElementsByTagName('tr') || [];

        for (let row of rows) {
            const text = row.textContent.toLowerCase();
            const status = row.querySelector('.badge')?.textContent.toLowerCase() || '';
            
            const matchesSearch = text.includes(searchText);
            const matchesStatus = !statusFilter || status.includes(statusFilter);
            
            row.style.display = (matchesSearch && matchesStatus) ? '' : 'none';
        }
    }

    document.getElementById('tableFilter')?.addEventListener('input', filterTable);
    document.getElementById('statusFilter')?.addEventListener('change', filterTable);

    // تحسين التنقل في النموذج
    const formInputs = document.querySelectorAll('form input, form select, form textarea');
    formInputs.forEach(input => {
        input.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                const inputs = Array.from(formInputs);
                const currentIndex = inputs.indexOf(this);
                const nextInput = inputs[currentIndex + 1];
                if (nextInput) nextInput.focus();
            }
        });
    });

    document.addEventListener('keydown', function(e) {
        if (e.ctrlKey && e.key === 's') {
            e.preventDefault();
            document.querySelector('form button[type="submit"]')?.click();
        }
    });

    // إضافة tooltips لجميع الأزرار
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    const tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
});
