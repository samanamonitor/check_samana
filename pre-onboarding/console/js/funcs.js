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
    $.getJSON('go/icons/' + sid, show_icons)
}

function show_printers(data) {
    tbody = $("#printers-table").find("tbody");
    tbody.html("");
    for(i=0; i < data.length; i++) {
        tbody.append(
            $("<tr>").append(
                    $("<td>").html(data[i]['Name'])
                ).append(
                    $("<td>").html(data[i]['ShareName'])
                )
            );
    }
}

function show_drives(data) {
    tbody = $("#drives-table").find("tbody");
    tbody.html("");
    for(i=0; i < data.length; i++) {
        if(data[i]['DisplayRoot'] == null) continue;
        tbody.append(
            $("<tr>").append(
                    $("<td>").html(data[i]['Name'])
                ).append(
                    $("<td>").html(data[i]['DisplayRoot'])
                )
            );
    }
}

function show_icons(data) {
    tbody = $("#icons-table").find("tbody");
    tbody.html("");
    for(i=0; i < data.length; i++) {
        tbody.append(
            $("<tr>").append(
                $("<td>").html(data[i])));
    }
}