function load_users() {
    $.getJSON('go/listusers', show_users);
}

function show_users(data) {
    u = $("#usertemplate").clone()
    u.removeClass("invisible");
    $("#userlist").append(u)
}