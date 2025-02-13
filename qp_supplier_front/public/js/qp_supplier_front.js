function openNav() {
    document.getElementById("mySidenav").style.width = "250px";
    document.getElementById("overlay").style.display = "block";
}

function closeNav() {
    document.getElementById("mySidenav").style.width = "0";
    document.getElementById("overlay").style.display = "none";
}


$(document).ready(function() {
    $('.number').on('input', function() {
        let value = $(this).val().replace(/\D/g, ''); // Eliminar cualquier carácter que no sea un número
        if (value.length > 0) {
            value = (parseInt(value) / 100).toFixed(2); // Convertir a decimal con dos decimales
        }
        $(this).val(value);
    });
});