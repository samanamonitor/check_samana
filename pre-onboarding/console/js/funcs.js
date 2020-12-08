function load_users() {
    $.getJSON('go/listusers', show_users);
}

function show_users(data) {
    for(i=0; i<data.length; i++) {
        u = $($("#usertemplate").html());
        user_name = u.find(".user-name");
        user_name.text(data[i]['samaccountname']);
        user_name.attr("sid", data[i]['sid']);
        u.click(show_data)
        $("#userlist").append(u)

    }
}

function show_data(e) {
    sid_object = $(e.target).find(".user-name");
    sid = sid_object.attr("sid");
    alert(sid);
}