// Category: Security Vulnerabilities
// Error: Hardcoded credentials

#include <iostream>
#include <string>

bool authenticate(const std::string& username, const std::string& password) {
    // ERROR: Hardcoded credentials - security vulnerability
    const std::string adminUser = "admin";
    const std::string adminPass = "password123";
    
    return (username == adminUser && password == adminPass);
}

int main() {
    std::string user, pass;
    
    std::cout << "Username: ";
    std::cin >> user;
    std::cout << "Password: ";
    std::cin >> pass;
    
    if (authenticate(user, pass)) {
        std::cout << "Access granted!" << std::endl;
    } else {
        std::cout << "Access denied." << std::endl;
    }
    
    return 0;
}
