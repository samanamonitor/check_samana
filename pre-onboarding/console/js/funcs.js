function load_users() {
    $.getJSON('go/listusers', function(data) {
        alert(data)
        }
    )
}