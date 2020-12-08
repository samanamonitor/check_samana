function load_users() {
    $.getJSON('go/listusers', show_users);
}

function show_users(data) {
    u = $($("#usertemplate").html());
    user_name = u.find(".user-name");
    user_name.text("hello");
    user_name.attr("sid", "asdf");
    $("#userlist").append(u)
}