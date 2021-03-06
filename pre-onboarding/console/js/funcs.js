function load_users() {
    $.getJSON('go/listusers', show_users);
}

function show_users(data) {
    for(i=0; i<data.length; i++) {
        u = $($("#usertemplate").html());
        user_name = u.find(".user-name");
        user_name.text(data[i]['samaccountname'] + " - " + data[i]['displayName'])
            .attr("sid", data[i]['sid'])
            .attr("displayName", user_name.text())
            .click(show_data);
        $("#userlist").append(u)
        view = u.find(".btn-primary")
        view.attr("sid", data[i]['sid'])
            .attr("displayName", user_name.text())
            .click(show_data);
        download = u.find(".btn-info");
        download.attr("sid", data[i]['sid'])
            .click(download_data);
    }
    $("#userlist").prepend(
        $("<button>").text("Download All")
            .addClass("btn btn-info btn-sm")
            .attr("type", "button")
            .click(download_all));
}

function show_data(e) {
    sid = $(e.target).attr("sid");
    username = $(e.target).attr("displayName");
    $(".modal").find(".modal-title").text(username);
    $(".modal").modal();
    $.getJSON('go/printers/' + sid, show_printers);
    $.getJSON('go/drives/' + sid, show_drives);
    $.getJSON('go/icons/' + sid, show_icons);
}

function download_data(e) {
    sid = $(e.target).attr("sid");
    document.location.replace('go/csv/' + sid);
}

function download_all(e) {
    document.location.replace('go/csvall/');
}

function show_printers(data) {
    tbody = $("#printers-table").find("tbody");
    tbody.html("");
    for(i=0; i < data.length; i++) {
        name=data[i]['Name']
        if("ShareName" in data[i] && data[i]["ShareName"] != null && data[i]["ShareName"] != ""){
            path=data[i]['ShareName'];
        }
        else if ("Location" in data[i]){
            path=data[i]["Location"];
        }
        tbody.append(
            $("<tr>").append(
                    $("<td>").html(name)
                ).append(
                    $("<td>").html(path)
                )
            );
    }
}

function show_drives(data) {
    tbody = $("#drives-table").find("tbody");
    tbody.html("");
    for(i=0; i < data.length; i++) {
        if("DisplayRoot" in data[i]){
            if(data[i]['DisplayRoot'] == null) continue;
            name=data[i]['Name'];
            path=data[i]['DisplayRoot'];
        } else {
            name=data[i]['LocalPath'];
            path=data[i]['RemotePath'];
        }
        tbody.append(
            $("<tr>").append(
                    $("<td>").html(name)
                ).append(
                    $("<td>").html(path)
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