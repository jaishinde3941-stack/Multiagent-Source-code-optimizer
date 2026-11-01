// Category: Memory Management Errors (Success Case)
// Expected Result: Ensure heap buffer has sufficient size

#include <iostream>
#include <cstring>

int main() {
    const char* message = "This string is too long for the buffer";
    char* buffer = new char[strlen(message) + 1];  // SUCCESS: Sufficient size
    
    strcpy(buffer, message);
    
    std::cout << buffer << std::endl;
    delete[] buffer;
    
    return 0;
}
