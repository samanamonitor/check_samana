function load_users() {
    $.getJSON('go/listusers', show_users);
}

function show_users(data) {
    for(i=0; i<data.length; i++) {
        u = $($("#usertemplate").html());
        user_name = u.find(".user-name");
        user_name.text(data[i]['samaccountname']);
        user_name.attr("sid", data[i]['sid']);
        user_name.click(show_data);
        $("#userlist").append(u)

    }
}

function show_data(e) {
    sid = $(e.target).attr("sid");
    username = $(e.target).text();
    $(".modal").find(".modal-title").text(username);
    $(".modal").modal();
    $.getJSON('go/printers/' + sid, show_printers);
    $.getJSON('go/drives/' + sid, show_drives);
}

function show_printers(data) {
    //alert(data);
}

function show_drives(data) {

}