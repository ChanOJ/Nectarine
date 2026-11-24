
   var showMode = 'table-cell';
   if (document.all) showMode='block';
   function toggleVis(btn){
        btn   = document.forms['tcol'].elements[btn];
        cells = document.getElementsByName('t'+btn.name);
        mode = btn.checked ? showMode : 'none';
        for(j = 0; j < cells.length; j++) cells[j].style.display = mode;
   }


// Calls a skintest cycle 
   function testSkin() 
   {
     var uploadApplet = this.document.UploadManager;
     if(uploadApplet) uploadApplet.callTestSkin();
   }

   function lien2(url) {
  var maitre; 
  if (opener.closed) {
    maitre=window.open('','nomprincipal','toolbar=yes, location=yes,status=yes,menubar=yes, scrollbars=yes,resizable=yes,copyhistory=no');
    maitre.location.href = url;
  } else {
    opener.location.href = url;
  }
}
function openrefused(idsong) {
window.open('/refused.htm?id='+idsong,'refused','height=250,width=300,scrollbars=yes,resizable=yes,toolbar=no,status=no,menubar=no');
}
function openfav(idsong) {
window.open('/fav.htm?idsong='+idsong,'favorite','height=200,width=250,scrollbars=no,resizable=yes,toolbar=no,status=no,menubar=no');
}
function openvote(idsong) {
window.open('/votepopup.htm?idsong='+idsong,'vote','height=200,width=250,scrollbars=no,resizable=yes,toolbar=no,status=no,menubar=no');
}
function openren(idsong) {
window.open('/rename.htm?idsong='+idsong,'rename','height=225,width=300,scrollbars=no,resizable=yes,toolbar=no,status=no,menubar=no');
}
function msgreq() {
window.open('/reqdj.htm','request','height=225,width=300,scrollbars=no,resizable=yes,toolbar=no,status=no,menubar=no');
}
function openauth(author) {
window.open('/infoauthor.htm?author='+author,'author','height=200,width=400,scrollbars=no,resizable=yes,toolbar=no,status=no,menubar=no');
}
function opentitres() {
opentitle = window.open('/magic.htm','titres','height=200,width=400,scrollbars=no,resizable=no,toolbar=no,status=no,menubar=no');
opentitle.focus();
}
function opensmiles() {
opentitle = window.open('/smiles.htm','smiles','height=400,width=250,scrollbars=no,resizable=no,toolbar=no,status=no,menubar=no');
opentitle.focus();
}
function OnChange(dropdown)
{
	var myindex  = dropdown.selectedIndex
	var SelValue = dropdown.options[myindex].value
	var baseURL  = ""
	top.location.href = SelValue;
	return true;
}
function openCodes(idsong) {
req = window.open('/req.htm?idsong='+idsong,'request2','height=200,width=280,scrollbars=no,resizable=no,toolbar=no,status=no,menubar=no');
req.focus();
}

function newmsgpopup(id) {
	msgpop = window.open('/message_write.htm?idlogin='+id,'msgpopup','toolbar=0,location=0,directories=0,status=0,menubar=0,scrollbars=1,resizable=1,width=500,height=500,left=' + (window.screen.width-500)/2 + ',top=' + (window.screen.height-400)/2);
}
function grouppopup(f)
{
 loginwin = window.open('/groups/a/groupslist.htm?field='+f,'loginwin','toolbar=0,location=0,directories=0,status=1,menubar=0,scrollbars=1,resizable=1,width=450,height=400,left=' + (window.screen.width-450)/2 + ',top=' + (window.screen.height-400)/2);
 loginwin.focus();
}
function DivStatus( nom, numero ) {
    var divID = nom + numero;
    var Pdiv = findDiv(divID);
    if (Pdiv) {
        Pdiv.className = (Pdiv.className == 'cachediv') ? '' : 'cachediv';
        saveDivStatus(divID,Pdiv.className);
    }
}
function getCookieName(){
    var cn = window.location.href;
    if(cn.indexOf('?')>-1){
        cn = cn.substring(0,cn.indexOf('?'));
    }
    cn = cn.substring(cn.lastIndexOf('/')+1,cn.length);
    if(cn == ''){ cn = 'index.htm'; }
    cn = 'di-'+cn;
    return cn;
}
function saveDivStatus(divId,className){
    //difo format: divId:className;divId:className;...
    var difo = gcv(getCookieName());
    var din = '';
    if(difo && difo.length > 0){
        var dix = difo.indexOf(divId);
        if(dix > -1){ //this exists in cookie, update that
            var darr = difo.split('-');
            for(i in darr){
                if(darr[i] && darr[i].length > 0 &&
darr[i].indexOf(divId) < 0){
                    din += darr[i]+'-';
                }
            }
        } else {
            din = difo
        }
    }
    din += divId+'.'+className+'-';
    sc(getCookieName(),din);
}
function loadUp(){
    var cv = gcv(getCookieName());
    if(cv && cv.length > 0){
        var darr = cv.split('-');
        for(i in darr){
         if(darr[i] && darr[i].length > 0){
            var di = darr[i].split('.');
            var dId = di[0];
            var dClass = di[1];
            if(dId && dClass && dId.length > 0 && dClass.length > 0){
                setDivStatus(dId,dClass);
            }
         }
        }
    }
}
function setDivStatus(divID,cName){
    var div = findDiv(divID);
    if(div){
        div.className = cName;
    }
}
function findDiv(divID){
    if ( document.getElementById && document.getElementById( divID ) ) {
        Pdiv = document.getElementById(divID);
    } else if ( document.all && document.all[divID] ){ 
        Pdiv = document.all[divID];
    } else if (document.layers && document.layers[divID]){ 
        Pdiv = document.layers[divID];
    }
    return Pdiv;
}
function gcv(cn){ try { return window.localStorage.getItem(cn); } catch (e) { return null; } }
function sc(cn,cv){ try { window.localStorage.setItem(cn, cv); } catch (e) { } }
function CacheTout( nom )
	{	
		var NumDiv = 1;
		if ( document.getElementById ) 
			{
				while ( document.getElementById( nom + NumDiv) )
					{
						SetDiv = document.getElementById( nom + NumDiv );
						if ( SetDiv && SetDiv.className != 'cachediv' )
							{
								DivStatus( nom, NumDiv );
							}
						NumDiv++;
					}
			}
		else if ( document.all ) 
			{
				while ( document.all[ nom + NumDiv ] )
					{
						SetDiv = document.all[ nom + NumDiv ];
						if ( SetDiv && SetDiv.className != 'cachediv' )
							{
								DivStatus( nom, NumDiv );
							}
						NumDiv++;
					}
			}
		else if ( document.layers ) 
			{
				while ( document.layers[ nom + NumDiv ] )
					{
						SetDiv = document.layers[ nom + NumDiv ];
						if ( SetDiv && SetDiv.className != 'cachediv' )
							{
								DivStatus( nom, NumDiv );
							}
						NumDiv++;
					}
			}
	}
function MontreTout( nom )
	{	
		var NumDiv = 1;
		if ( document.getElementById ) 
			{
				while ( document.getElementById( nom + NumDiv) )
					{
						SetDiv = document.getElementById( nom + NumDiv );
						if ( SetDiv && SetDiv.className != '' )
							{
								DivStatus( nom, NumDiv );
							}
						NumDiv++;
					}
			}
		else if ( document.all ) 
			{
				while ( document.all[ nom + NumDiv ] )
					{
						SetDiv = document.all[ nom + NumDiv ];
						if ( SetDiv && SetDiv.className != '' )
							{
								DivStatus( nom, NumDiv );
							}
						NumDiv++;
					}
			}
		else if ( document.layers ) 
			{
				while ( document.layers[ nom + NumDiv ] )
					{
						SetDiv = document.layers[ nom + NumDiv ];
						if ( SetDiv && SetDiv.className != '' )
							{
								DivStatus( nom, NumDiv );
							}
						NumDiv++;
					}
			}
	}
function id2element(id)
{
    if (!document.getElementById)
        return;

    if (document.all)
        return eval("document.all." + id);
    else
        return document.getElementById(id);
}

function toggle_msg(id) {
    id2element("mondiv" + id).style.display = (id2element("mondiv" + id).style.display == "none" ? "block" : "none");
}


  // Sets focus on comments field if should be filled out
  function focusComments()
  {
    if((this.document.uploadform.conversion.value==2
    || this.document.uploadform.uploadtype.value==2)
    && this.document.uploadform.conversion.value != ""
    && this.document.uploadform.uploadtype.value != ""
    ) 
      this.document.uploadform.comments.focus();
  }

  // Calls the applet that does the job
  function uploadFile()
  {
    var uploadApplet = this.document.UploadManager;
    if(uploadApplet) 
    {
      uploadApplet.getSongInfo().setFilename(this.document.uploadform.userfile.value);
      uploadApplet.getSongInfo().setTitle(this.document.uploadform.title.value);
      uploadApplet.getSongInfo().setCompoYear(this.document.uploadform.year.value);
      uploadApplet.getSongInfo().setDlLink(this.document.uploadform.link.value);
      uploadApplet.getSongInfo().setIdPlatform(this.document.uploadform.platform.value);
      uploadApplet.getSongInfo().setIdCategory(this.document.uploadform.category.value);
      uploadApplet.getSongInfo().setIdUploadType(this.document.uploadform.uploadtype.value);
      uploadApplet.getSongInfo().setIdConvMode(this.document.uploadform.conversion.value);
	  uploadApplet.getSongInfo().setIdToUpdate(this.document.uploadform.updateid.value);
      uploadApplet.getSongInfo().setComments(this.document.uploadform.comments.value);
      uploadApplet.getSongInfo().setIdPouet(this.document.uploadform.pouet.value);
      uploadApplet.callUpload();
    }
  }

function call(strCall)
{
  var retrieveApplet = this.document.UploadRetrieveManager;
  if(retrieveApplet) 
  {
    if(strCall=="retrieve")
    {
      if(confirm("Do you really want to RETRIEVE THE CSV now?")) retrieveApplet.call(strCall);
    }
    else retrieveApplet.call(strCall);
  }
}


 function commit() 
{ 
  var commitApplet = this.document.UploadCommitManager; 
  if(commitApplet)  
  { 
     if(confirm("Really commit ALL?")) commitApplet.callCommit(); 
  } 
} 

function commitRejected()
{
  var commitApplet = this.document.UploadCommitManager; 
  if(commitApplet)  
  { 
     commitApplet.callRemoveRejectedOnyl(); 
  }   
}


function set(n)
{
	temp = document.main.elements.length ;
	for (i=0; i < temp; i++)
	{ document.main.elements[i].checked=n;
	}
}

function Invers()
{

	temp = document.main.elements.length ;
	for (i=0; i < temp; i++)
	{
	if(document.main.elements[i].checked == 1){document.main.elements[i].checked = 0;}
	else {document.main.elements[i].checked = 1}
	}
}

function a(p) { opener.document.f_withidlogin.idlogin.value=p; opener.focus(); self.close(); }
function m(p) { window.status='idlogin = '+p; return true; }

function loginpopup()
{
 loginwin = window.open('loginlist.htm','loginwin','toolbar=0,location=0,directories=0,status=1,menubar=0,scrollbars=1,resizable=1,width=450,height=400,left=' + (window.screen.width-450)/2 + ',top=' + (window.screen.height-400)/2);
 loginwin.focus();
}
