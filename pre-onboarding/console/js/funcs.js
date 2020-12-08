function load_users() {
    $.getJSON('go/listusers', show_users);
}

function show_users(data) {
    u = $("#usertemplate").html().clone();
    $("#userlist").append(u)
}